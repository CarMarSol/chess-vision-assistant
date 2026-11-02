"""Referencias medidas del juego Neo aportado por el usuario, sin priorizar casillas."""

from functools import lru_cache
from pathlib import Path
import sys

import chess
import cv2
import numpy as np


def extract_reference_features(image):
    """Separa la pieza del fondo y normaliza silueta, detalle y luminosidad."""
    if image is None or image.size == 0 or min(image.shape[:2]) < 16:
        return None
    image = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    corners = np.concatenate([
        image[:8, :8].reshape(-1, 3), image[:8, -8:].reshape(-1, 3),
        image[-8:, :8].reshape(-1, 3), image[-8:, -8:].reshape(-1, 3),
    ])
    bins = corners // 8
    values, counts = np.unique(bins, axis=0, return_counts=True)
    background = np.median(corners[np.all(bins == values[counts.argmax()], axis=1)], axis=0)
    contrast = np.max(np.abs(image.astype(float) - background), axis=2)
    # Las piezas son grises; letras, resaltados y flechas del tablero tienen color.
    foreground = ((contrast > 22) & (np.ptp(image.astype(float), axis=2) < 18)).astype(np.uint8)
    closed = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    count, labels, stats, centers = cv2.connectedComponentsWithStats(closed)
    candidates = [i for i in range(1, count)
                  if abs(centers[i, 0] - 32) < 16 and stats[i, cv2.CC_STAT_AREA] >= 40]
    if not candidates:
        return None
    largest = max(candidates, key=lambda i: stats[i, cv2.CC_STAT_AREA])
    contours, _ = cv2.findContours((labels == largest).astype(np.uint8), cv2.RETR_EXTERNAL,
                                  cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros((64, 64), np.uint8)
    cv2.drawContours(filled, contours, -1, 1, -1)
    ys, xs = np.where(filled)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    if y1 - y0 < 22 or x1 - x0 < 10:
        return None
    silhouette = cv2.resize(filled[y0:y1, x0:x1], (32, 32), interpolation=cv2.INTER_NEAREST) > 0
    detail = cv2.resize(foreground[y0:y1, x0:x1], (32, 32), interpolation=cv2.INTER_NEAREST) > 0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    tones = cv2.resize(gray[y0:y1, x0:x1], (32, 32), interpolation=cv2.INTER_AREA)
    return silhouette, detail, tones, (x1 - x0) / (y1 - y0), (y1 - y0) / 64


@lru_cache(maxsize=1)
def _load_references():
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    path = root / "data" / "templates" / "chesscom_neo_references.npz"
    if not path.is_file():
        return None
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in ("symbols", "silhouettes", "details", "tones", "aspects", "heights")}


@lru_cache(maxsize=256)
def _reference_scores(pixels):
    data = _load_references()
    if data is None:
        return ()
    image = np.frombuffer(pixels, dtype=np.uint8).reshape(64, 64, 3)
    features = extract_reference_features(image)
    if features is None:
        return ()
    silhouette, detail, tones, aspect, height = features
    shape_iou = np.sum(silhouette & data["silhouettes"], axis=(1, 2)) / np.maximum(
        1, np.sum(silhouette | data["silhouettes"], axis=(1, 2)))
    detail_iou = np.sum(detail & data["details"], axis=(1, 2)) / np.maximum(
        1, np.sum(detail | data["details"], axis=(1, 2)))
    common = detail & data["details"]
    tone_difference = np.abs(tones.astype(float) - data["tones"].astype(float))
    brightness = 1 - np.sum(tone_difference * common, axis=(1, 2)) / np.maximum(
        1, np.sum(common, axis=(1, 2))) / 255
    scores = (0.65 * shape_iou + 0.15 * detail_iou + 0.20 * brightness
              - 0.15 * np.abs(np.log(aspect / data["aspects"]))
              - 0.10 * np.abs(height - data["heights"]))
    by_symbol = {}
    for symbol, score in zip(data["symbols"], scores):
        by_symbol[str(symbol)] = max(by_symbol.get(str(symbol), 0.0), float(score))
    return tuple(sorted(by_symbol.items(), key=lambda item: item[1], reverse=True))


def get_reference_ranking(image, color=None):
    """Devuelve evidencia medida solo cuando supera el umbral y al segundo candidato.

    Un tema distinto o una imagen ambigua conserva el clasificador existente.
    Las puntuaciones son similitudes visuales, no probabilidades estadísticas.
    """
    if image is None or image.size == 0 or min(image.shape[:2]) < 16:
        return []
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    canonical = cv2.resize(image, (64, 64), interpolation=cv2.INTER_AREA)
    ranking = [(chess.Piece.from_symbol(symbol), score) for symbol, score in _reference_scores(canonical.tobytes())
               if color is None or symbol.isupper() == color]
    if len(ranking) < 2 or ranking[0][1] < 0.88 or ranking[0][1] - ranking[1][1] < 0.04:
        return []
    return ranking
