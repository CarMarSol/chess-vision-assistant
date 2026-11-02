"""Interface translations; chess notation and stored configuration stay unchanged."""

from __future__ import annotations

import re

LANGUAGES = {
    "es": "Español",
    "en": "English",
    "fr": "Français",
    "pt": "Português",
    "de": "Deutsch",
}
_language = "es"

# Each row is Spanish, English, French, Portuguese, German. Keep placeholders intact.
_MESSAGES = (
    ("Los diseños de piezas exóticos pueden no reconocerse. Prueba piezas cburnett o consulta el manual para adaptar las referencias con tu IA.", "Exotic piece designs may not be recognized. Try cburnett pieces or see the manual to adapt the references with your AI.", "Les pièces au design inhabituel peuvent ne pas être reconnues. Essayez les pièces cburnett ou consultez le manuel pour adapter les références avec votre IA.", "Peças com desenhos exóticos podem não ser reconhecidas. Experimente peças cburnett ou consulte o manual para adaptar as referências com sua IA.", "Ungewöhnliche Figurendesigns werden möglicherweise nicht erkannt. Verwenden Sie cburnett-Figuren oder passen Sie die Vorlagen mithilfe Ihrer KI nach der Anleitung an."),
    ("Idioma", "Language", "Langue", "Idioma", "Sprache"),
    ("Idioma de la interfaz", "Interface language", "Langue de l’interface", "Idioma da interface", "Sprache der Oberfläche"),
    ("Idioma guardado", "Language saved", "Langue enregistrée", "Idioma salvo", "Sprache gespeichert"),
    ("El idioma se aplicará al reiniciar la aplicación. El seguimiento actual continúa sin cambios.", "The language will apply when you restart the application. Current tracking continues unchanged.", "La langue sera appliquée au redémarrage de l’application. Le suivi actuel continue sans changement.", "O idioma será aplicado ao reiniciar o aplicativo. O acompanhamento atual continua sem alterações.", "Die Sprache wird beim nächsten Start angewendet. Die aktuelle Erfassung läuft unverändert weiter."),
    ("No se pudo guardar el idioma. Comprueba los permisos de la carpeta de configuración.", "Could not save the language. Check the configuration folder permissions.", "Impossible d’enregistrer la langue. Vérifiez les droits du dossier de configuration.", "Não foi possível salvar o idioma. Verifique as permissões da pasta de configuração.", "Die Sprache konnte nicht gespeichert werden. Prüfen Sie die Rechte des Konfigurationsordners."),
    ("Tablero {number}", "Board {number}", "Échiquier {number}", "Tabuleiro {number}", "Brett {number}"),
    ("  Tableros Activos: ", "  Active boards: ", "  Échiquiers actifs : ", "  Tabuleiros ativos: ", "  Aktive Bretter: "),
    ("1 Tablero", "1 board", "1 échiquier", "1 tabuleiro", "1 Brett"),
    ("2 Tableros", "2 boards", "2 échiquiers", "2 tabuleiros", "2 Bretter"),
    ("3 Tableros", "3 boards", "3 échiquiers", "3 tabuleiros", "3 Bretter"),
    ("4 Tableros", "4 boards", "4 échiquiers", "4 tabuleiros", "4 Bretter"),
    ("<b>Bienvenido a Chess Vision Assistant</b><br>Selecciona el número de tableros a seguir y el modo de visualización deseado.", "<b>Welcome to Chess Vision Assistant</b><br>Choose the number of boards to track and the display mode.", "<b>Bienvenue dans Chess Vision Assistant</b><br>Choisissez le nombre d’échiquiers à suivre et le mode d’affichage.", "<b>Bem-vindo ao Chess Vision Assistant</b><br>Escolha o número de tabuleiros e o modo de exibição.", "<b>Willkommen bei Chess Vision Assistant</b><br>Wählen Sie die Anzahl der Bretter und den Anzeigemodus."),
    ("Abrir asistente inicial para configurar tableros, modos y regiones", "Open setup for boards, display modes and screen regions", "Configurer les échiquiers, les modes et les zones d’écran", "Configurar tabuleiros, modos e regiões de tela", "Bretter, Anzeigemodi und Bildschirmbereiche einrichten"),
    ("Abrir panel de configuración de nivel de Elo (700-2800), Estilo y Motor", "Configure Elo level (700–2800), style and engine", "Configurer le niveau Elo (700–2800), le style et le moteur", "Configurar nível Elo (700–2800), estilo e motor", "Elo-Stärke (700–2800), Stil und Engine einstellen"),
    ("Abrir selector estilo Snipping Tool para capturar tablero en pantalla", "Select a screen region to capture a board", "Sélectionner une zone d’écran pour capturer l’échiquier", "Selecionar uma região da tela para capturar o tabuleiro", "Bildschirmbereich für die Bretterfassung auswählen"),
    ("Abrir simulador con tácticas célebres para probar sin navegador", "Open tactical positions for testing without a browser", "Ouvrir des positions tactiques sans navigateur", "Abrir posições táticas para testar sem navegador", "Taktikstellungen zum Testen ohne Browser öffnen"),
    ("Activar jugada adaptativa por precisión objetivo", "Enable adaptive move by target accuracy", "Activer le coup adaptatif selon la précision cible", "Ativar lance adaptativo por precisão alvo", "Adaptiven Zug nach Zielgenauigkeit aktivieren"),
    ("Activar o desactivar superposición de flechas directamente sobre la pantalla", "Toggle arrows over the captured screen region", "Afficher ou masquer les flèches sur la zone capturée", "Ativar ou desativar setas sobre a região capturada", "Pfeile über dem erfassten Bildschirmbereich ein- oder ausblenden"),
    ("Agresivo (Ataque)", "Aggressive (Attack)", "Agressif (Attaque)", "Agressivo (Ataque)", "Aggressiv (Angriff)"),
    ("Alto (Profundo, depth 16)", "High (Deep, depth 16)", "Élevé (Profond, profondeur 16)", "Alto (Profundo, profundidade 16)", "Hoch (Gründlich, Tiefe 16)"),
    ("Análisis Multi-PV", "Multi-PV analysis", "Analyse Multi-PV", "Análise Multi-PV", "Multi-PV-Analyse"),
    ("Auto (Detección automática)", "Auto (Automatic detection)", "Auto (Détection automatique)", "Auto (Detecção automática)", "Auto (Automatische Erkennung)"),
    ("Avanzado (88%)", "Advanced (88%)", "Avancé (88%)", "Avançado (88%)", "Fortgeschritten (88%)"),
    ("Azul Clásico", "Classic blue", "Bleu classique", "Azul clássico", "Klassisches Blau"),
    ("Bajo (Rápido, depth 8)", "Low (Fast, depth 8)", "Faible (Rapide, profondeur 8)", "Baixo (Rápido, profundidade 8)", "Niedrig (Schnell, Tiefe 8)"),
    ("Barra de Herramientas", "Toolbar", "Barre d’outils", "Barra de ferramentas", "Werkzeugleiste"),
    ("Blancas abajo", "White at bottom", "Blancs en bas", "Brancas embaixo", "Weiß unten"),
    ("Cambiar a Modo Claro", "Switch to light mode", "Passer au thème clair", "Mudar para modo claro", "Zum hellen Modus wechseln"),
    ("Cambiar a Modo Oscuro", "Switch to dark mode", "Passer au thème sombre", "Mudar para modo escuro", "Zum dunklen Modus wechseln"),
    ("Cancelar", "Cancel", "Annuler", "Cancelar", "Abbrechen"),
    ("Cargar FEN", "Load FEN", "Charger le FEN", "Carregar FEN", "FEN laden"),
    ("Cargar Posición Predefinida:", "Load preset position:", "Charger une position prédéfinie :", "Carregar posição predefinida:", "Voreingestellte Stellung laden:"),
    ("Casilla {value0} ({value1})", "Square {value0} ({value1})", "Case {value0} ({value1})", "Casa {value0} ({value1})", "Feld {value0} ({value1})"),
    ("Cerrar", "Close", "Fermer", "Fechar", "Schließen"),
    ("Chess Vision Assistant - Análisis y Visión en Tiempo Real", "Chess Vision Assistant - Real-Time Vision and Analysis", "Chess Vision Assistant - Vision et analyse en temps réel", "Chess Vision Assistant - Visão e análise em tempo real", "Chess Vision Assistant - Erkennung und Analyse in Echtzeit"),
    ("Club (72%)", "Club (72%)", "Club (72%)", "Clube (72%)", "Verein (72%)"),
    ("Configuración: {value0}", "Settings: {value0}", "Paramètres : {value0}", "Configurações: {value0}", "Einstellungen: {value0}"),
    ("Conmutar entre Modo Oscuro y Modo Claro", "Toggle dark and light mode", "Alterner entre les thèmes sombre et clair", "Alternar modos escuro e claro", "Zwischen dunklem und hellem Modus wechseln"),
    ("Defensivo (Sólido)", "Defensive (Solid)", "Défensif (Solide)", "Defensivo (Sólido)", "Defensiv (Solide)"),
    ("Deshacer", "Undo", "Annuler le coup", "Desfazer", "Zug zurücknehmen"),
    ("Ejecutar Jugada en Tablero:", "Play move on board:", "Jouer un coup sur l’échiquier :", "Executar lance no tabuleiro:", "Zug auf dem Brett ausführen:"),
    ("Equilibrado (Standard)", "Balanced (Standard)", "Équilibré (Standard)", "Equilibrado (Padrão)", "Ausgewogen (Standard)"),
    ("Escanear las 64 fichas de la pantalla física y reconstruir la posición FEN exacta", "Scan all 64 squares and reconstruct the FEN position", "Analyser les 64 cases et reconstruire la position FEN", "Analisar as 64 casas e reconstruir a posição FEN", "Alle 64 Felder erfassen und die FEN-Stellung rekonstruieren"),
    ("Escaneo automático en tiempo real", "Automatic real-time scanning", "Analyse visuelle automatique en temps réel", "Varredura automática em tempo real", "Automatische Erfassung in Echtzeit"),
    ("Esfuerzo de cálculo:", "Analysis effort:", "Effort de calcul :", "Esforço de cálculo:", "Rechenaufwand:"),
    ("Estilo de juego:", "Playing style:", "Style de jeu :", "Estilo de jogo:", "Spielstil:"),
    ("Estilo de tablero:", "Board theme:", "Thème de l’échiquier :", "Tema do tabuleiro:", "Brettdesign:"),
    ("FEN Actual:", "Current FEN:", "FEN actuel :", "FEN atual:", "Aktuelles FEN:"),
    ("Forzar re-análisis en todos los tableros activos", "Reanalyze all active boards", "Relancer l’analyse de tous les échiquiers actifs", "Reanalisar todos os tabuleiros ativos", "Alle aktiven Bretter erneut analysieren"),
    ("Forzar re-sincronización y comprobación completa del tablero actual", "Resynchronize and check the current board", "Resynchroniser et vérifier l’échiquier actuel", "Ressincronizar e verificar o tabuleiro atual", "Aktuelles Brett neu synchronisieren und prüfen"),
    ("General", "General", "Général", "Geral", "Allgemein"),
    ("Guardar Cambios", "Save changes", "Enregistrer", "Salvar alterações", "Änderungen speichern"),
    ("Hacer Jugada", "Play move", "Jouer le coup", "Executar lance", "Zug ausführen"),
    ("Hacer clic para cambiar Nivel de Elo (700-2800), Estilo de juego y Esfuerzo de Stockfish", "Change Elo level (700–2800), playing style and Stockfish effort", "Modifier le niveau Elo (700–2800), le style et l’effort de Stockfish", "Alterar nível Elo (700–2800), estilo e esforço do Stockfish", "Elo-Stärke (700–2800), Spielstil und Stockfish-Aufwand ändern"),
    ("Indicaciones superpuestas (flechas directamente sobre tu pantalla)", "Overlay (arrows directly on your screen)", "Superposition (flèches sur votre écran)", "Sobreposição (setas diretamente na tela)", "Überlagerung (Pfeile direkt auf dem Bildschirm)"),
    ("Indicaciones superpuestas (overlay sobre pantalla)", "Overlay on screen", "Indications superposées à l’écran", "Indicações sobrepostas na tela", "Hinweise über dem Bildschirm"),
    ("Inicializando motor Stockfish...", "Starting Stockfish engine...", "Démarrage du moteur Stockfish...", "Iniciando motor Stockfish...", "Stockfish-Engine wird gestartet..."),
    ("Intermedio (80%)", "Intermediate (80%)", "Intermédiaire (80%)", "Intermediário (80%)", "Mittel (80%)"),
    ("Intervalo de escaneo (ms):", "Scan interval (ms):", "Intervalle de capture (ms) :", "Intervalo de varredura (ms):", "Erfassungsintervall (ms):"),
    ("Invertir orientación del tablero (Blancas/Negras)", "Flip board orientation (White/Black)", "Inverser l’orientation (Blancs/Noirs)", "Inverter orientação (brancas/pretas)", "Brettausrichtung umkehren (Weiß/Schwarz)"),
    ("Inyectar Posición a Chess Vision", "Send position to Chess Vision", "Envoyer la position à Chess Vision", "Enviar posição ao Chess Vision", "Stellung an Chess Vision senden"),
    ("Madera Lichess", "Lichess wood", "Bois Lichess", "Madeira Lichess", "Lichess-Holz"),
    ("Maestro (94%)", "Master (94%)", "Maître (94%)", "Mestre (94%)", "Meister (94%)"),
    ("Medio (Equilibrado, depth 12)", "Medium (Balanced, depth 12)", "Moyen (Équilibré, profondeur 12)", "Médio (Equilibrado, profundidade 12)", "Mittel (Ausgewogen, Tiefe 12)"),
    ("Mejor jugada", "Best move", "Meilleur coup", "Melhor lance", "Bester Zug"),
    ("Modo de visualización:", "Display mode:", "Mode d’affichage :", "Modo de exibição:", "Anzeigemodus:"),
    ("Monocromo", "Monochrome", "Monochrome", "Monocromático", "Monochrom"),
    ("Mostrar barra de evaluación lateral", "Show evaluation bar", "Afficher la barre d’évaluation", "Mostrar barra de avaliação", "Bewertungsbalken anzeigen"),
    ("Mostrar flechas tácticas en el tablero", "Show tactical arrows on board", "Afficher les flèches tactiques", "Mostrar setas táticas no tabuleiro", "Taktische Pfeile auf dem Brett anzeigen"),
    ("Motor & Estilo de Juego", "Engine and playing style", "Moteur et style de jeu", "Motor e estilo de jogo", "Engine und Spielstil"),
    ("Motor: {value0}", "Engine: {value0}", "Moteur : {value0}", "Motor: {value0}", "Engine: {value0}"),
    ("Muy alto (Torneo, depth 20)", "Very high (Tournament, depth 20)", "Très élevé (Tournoi, profondeur 20)", "Muito alto (Torneio, profundidade 20)", "Sehr hoch (Turnier, Tiefe 20)"),
    ("Negras abajo", "Black at bottom", "Noirs en bas", "Pretas embaixo", "Schwarz unten"),
    ("Nivel Elo:", "Elo level:", "Niveau Elo :", "Nível Elo:", "Elo-Stärke:"),
    ("Nombre:", "Name:", "Nom :", "Nome:", "Name:"),
    ("Número de tableros simultáneos:", "Number of simultaneous boards:", "Nombre d’échiquiers simultanés :", "Número de tabuleiros simultâneos:", "Anzahl gleichzeitiger Bretter:"),
    ("Orientación:", "Orientation:", "Orientation :", "Orientação:", "Ausrichtung:"),
    ("Pausar o reanudar el escaneo continuo en pantalla", "Pause or resume continuous scanning", "Suspendre ou reprendre la capture continue", "Pausar ou retomar a varredura contínua", "Laufende Erfassung pausieren oder fortsetzen"),
    ("Perfil predefinido:", "Preset profile:", "Profil prédéfini :", "Perfil predefinido:", "Voreingestelltes Profil:"),
    ("Personalizado", "Custom", "Personnalisé", "Personalizado", "Benutzerdefiniert"),
    ("Posicional (Estratégico)", "Positional (Strategic)", "Positionnel (Stratégique)", "Posicional (Estratégico)", "Positionell (Strategisch)"),
    ("Posición FEN inyectada en {value0}", "FEN position sent to {value0}", "Position FEN envoyée à {value0}", "Posição FEN enviada para {value0}", "FEN-Stellung an {value0} gesendet"),
    ("Precisión objetivo:", "Target accuracy:", "Précision cible :", "Precisão alvo:", "Zielgenauigkeit:"),
    ("Región asignada a {value0}: ({value1}, {value2}, {value3}x{value4})", "Region assigned to {value0}: ({value1}, {value2}, {value3}x{value4})", "Zone affectée à {value0} : ({value1}, {value2}, {value3}x{value4})", "Região atribuída a {value0}: ({value1}, {value2}, {value3}x{value4})", "Bereich für {value0}: ({value1}, {value2}, {value3}x{value4})"),
    ("Región: ", "Region: ", "Zone : ", "Região: ", "Bereich: "),
    ("Región: ({value0}, {value1}, {value2}x{value3})", "Region: ({value0}, {value1}, {value2}x{value3})", "Zone : ({value0}, {value1}, {value2}x{value3})", "Região: ({value0}, {value1}, {value2}x{value3})", "Bereich: ({value0}, {value1}, {value2}x{value3})"),
    ("Reiniciar a posición inicial y recalibrar", "Reset to starting position and recalibrate", "Revenir à la position initiale et recalibrer", "Voltar à posição inicial e recalibrar", "Ausgangsstellung wiederherstellen und neu kalibrieren"),
    ("Seleccionar región de pantalla con recortes", "Select a screen region", "Sélectionner une zone d’écran", "Selecionar região da tela", "Bildschirmbereich auswählen"),
    ("Selector de perspectiva: Auto-detectar, o fijar Blancas / Negras abajo", "Perspective: automatic, White at bottom or Black at bottom", "Perspective : automatique, Blancs en bas ou Noirs en bas", "Perspectiva: automática, brancas ou pretas embaixo", "Perspektive: automatisch, Weiß unten oder Schwarz unten"),
    ("Simulación y precisión objetivo", "Simulation and target accuracy", "Simulation et précision cible", "Simulação e precisão alvo", "Simulation und Zielgenauigkeit"),
    ("Simulador de Partidas y Pruebas Tácticas", "Game and tactical position simulator", "Simulateur de parties et de tactiques", "Simulador de partidas e testes táticos", "Partie- und Taktiksimulator"),
    ("Sin asignar", "Not assigned", "Non affectée", "Não atribuída", "Nicht zugewiesen"),
    ("Tablero independiente (reproducción interna en ventana)", "Independent board (inside the application)", "Échiquier indépendant (dans la fenêtre)", "Tabuleiro independente (dentro da janela)", "Unabhängiges Brett (im Anwendungsfenster)"),
    ("Tablero independiente (reproducción interna)", "Independent board (internal display)", "Échiquier indépendant (affichage interne)", "Tabuleiro independente (exibição interna)", "Unabhängiges Brett (interne Anzeige)"),
    ("Tablero {value0}: {value1}", "Board {value0}: {value1}", "Échiquier {value0} : {value1}", "Tabuleiro {value0}: {value1}", "Brett {value0}: {value1}"),
    ("Táctico (Dinámico)", "Tactical (Dynamic)", "Tactique (Dynamique)", "Tático (Dinâmico)", "Taktisch (Dynamisch)"),
    ("Verde Chess.com", "Chess.com green", "Vert Chess.com", "Verde Chess.com", "Chess.com-Grün"),
    ("Visualización y Captura", "Display and capture", "Affichage et capture", "Exibição e captura", "Anzeige und Erfassung"),
    ("Win: 50%", "Win: 50%", "Gain : 50%", "Vitória: 50%", "Sieg: 50%"),
    ("Win: {value0:.1f}%", "Win: {value0:.1f}%", "Gain : {value0:.1f}%", "Vitória: {value0:.1f}%", "Sieg: {value0:.1f}%"),
    ("d: 0", "d: 0", "p : 0", "p: 0", "T: 0"),
    ("d: {value0}", "d: {value0}", "p : {value0}", "p: {value0}", "T: {value0}"),
    ("Última: --", "Last: --", "Dernier : --", "Último: --", "Letzter: --"),
    ("Última: {value0:.0f}%", "Last: {value0:.0f}%", "Dernier : {value0:.0f}%", "Último: {value0:.0f}%", "Letzter: {value0:.0f}%"),
    ("↺ Posición Inicial", "↺ Starting position", "↺ Position initiale", "↺ Posição inicial", "↺ Ausgangsstellung"),
    ("↺ Reiniciar", "↺ Reset", "↺ Réinitialiser", "↺ Reiniciar", "↺ Zurücksetzen"),
    ("⌛ Posición pendiente de confirmar", "⌛ Waiting to confirm position", "⌛ Position en attente de confirmation", "⌛ Aguardando confirmação da posição", "⌛ Stellung wird noch bestätigt"),
    ("⏸ Pausar", "⏸ Pause", "⏸ Pause", "⏸ Pausar", "⏸ Pausieren"),
    ("▶ Reanudar", "▶ Resume", "▶ Reprendre", "▶ Retomar", "▶ Fortsetzen"),
    ("● EN VIVO (Sincronizado +{value0})", "● LIVE (Synchronized +{value0})", "● DIRECT (Synchronisé +{value0})", "● AO VIVO (Sincronizado +{value0})", "● LIVE (Synchronisiert +{value0})"),
    ("● EN VIVO (Sincronizado)", "● LIVE (Synchronized)", "● DIRECT (Synchronisé)", "● AO VIVO (Sincronizado)", "● LIVE (Synchronisiert)"),
    ("● EN VIVO · Tablero mental activo ({value0} piezas)", "● LIVE · Board tracking active ({value0} pieces)", "● DIRECT · Suivi actif ({value0} pièces)", "● AO VIVO · Acompanhamento ativo ({value0} peças)", "● LIVE · Bretterfassung aktiv ({value0} Figuren)"),
    ("● Edición manual (Pausado)", "● Manual editing (Paused)", "● Modification manuelle (Pause)", "● Edição manual (Pausado)", "● Manuelle Bearbeitung (Pausiert)"),
    ("● Escaneo en pausa", "● Scanning paused", "● Capture en pause", "● Varredura pausada", "● Erfassung pausiert"),
    ("● Jugada: {value0}{value1}", "● Move: {value0}{value1}", "● Coup : {value0}{value1}", "● Lance: {value0}{value1}", "● Zug: {value0}{value1}"),
    ("● Listo", "● Ready", "● Prêt", "● Pronto", "● Bereit"),
    ("☀️ Modo Claro", "☀️ Light mode", "☀️ Thème clair", "☀️ Modo claro", "☀️ Heller Modus"),
    ("♙ Blancas abajo", "♙ White at bottom", "♙ Blancs en bas", "♙ Brancas embaixo", "♙ Weiß unten"),
    ("♟ Negras abajo", "♟ Black at bottom", "♟ Noirs en bas", "♟ Pretas embaixo", "♟ Schwarz unten"),
    ("♟ Simulador de Partidas", "♟ Game simulator", "♟ Simulateur de parties", "♟ Simulador de partidas", "♟ Partiesimulator"),
    ("⚙ Ajustes · Elo: {value0}", "⚙ Settings · Elo: {value0}", "⚙ Paramètres · Elo : {value0}", "⚙ Ajustes · Elo: {value0}", "⚙ Einstellungen · Elo: {value0}"),
    ("⚙ Configurar Elo y Ajustes", "⚙ Elo and settings", "⚙ Elo et paramètres", "⚙ Elo e ajustes", "⚙ Elo und Einstellungen"),
    ("⚠ Desincronizado", "⚠ Out of sync", "⚠ Désynchronisé", "⚠ Dessincronizado", "⚠ Nicht synchronisiert"),
    ("⚠ Error al capturar pantalla", "⚠ Screen capture failed", "⚠ Échec de capture d’écran", "⚠ Falha na captura de tela", "⚠ Bildschirmaufnahme fehlgeschlagen"),
    ("⚠ Escaneo dudoso - Ajusta la posición si es necesario", "⚠ Uncertain scan - Correct the position if needed", "⚠ Capture incertaine - Corrigez la position si nécessaire", "⚠ Leitura incerta - Corrija a posição se necessário", "⚠ Unsichere Erkennung - Stellung bei Bedarf korrigieren"),
    ("⚠ Selecciona región primero", "⚠ Select a region first", "⚠ Sélectionnez d’abord une zone", "⚠ Selecione uma região primeiro", "⚠ Zuerst einen Bereich auswählen"),
    ("⚡ REC", "⚡ REC", "⚡ REC", "⚡ REC", "⚡ EMPF"),
    ("⚪ Blancas", "⚪ White", "⚪ Blancs", "⚪ Brancas", "⚪ Weiß"),
    ("⚪ Piezas Blancas", "⚪ White pieces", "⚪ Pièces blanches", "⚪ Peças brancas", "⚪ Weiße Figuren"),
    ("⚫ Negras", "⚫ Black", "⚫ Noirs", "⚫ Pretas", "⚫ Schwarz"),
    ("⚫ Piezas Negras", "⚫ Black pieces", "⚫ Pièces noires", "⚫ Peças pretas", "⚫ Schwarze Figuren"),
    ("✂ Recortar", "✂ Select region", "✂ Découper", "✂ Recortar", "✂ Bereich wählen"),
    ("✂ Seleccionar Pantalla", "✂ Select screen region", "✂ Sélectionner une zone", "✂ Selecionar região", "✂ Bildschirmbereich wählen"),
    ("✂ Seleccionar región", "✂ Select region", "✂ Sélectionner une zone", "✂ Selecionar região", "✂ Bereich wählen"),
    ("⟳ Analizar Todo", "⟳ Analyze all", "⟳ Tout analyser", "⟳ Analisar tudo", "⟳ Alles analysieren"),
    ("⟳ Auto", "⟳ Auto", "⟳ Auto", "⟳ Auto", "⟳ Auto"),
    ("⟳ Girar", "⟳ Flip", "⟳ Retourner", "⟳ Girar", "⟳ Drehen"),
    ("🌙 Modo Oscuro", "🌙 Dark mode", "🌙 Thème sombre", "🌙 Modo escuro", "🌙 Dunkler Modus"),
    ("🎯 Asistente de Inicio / Modos", "🎯 Setup / Modes", "🎯 Assistant / Modes", "🎯 Assistente / Modos", "🎯 Einrichtung / Modi"),
    ("🎯 Asistente de Inicio / Modos de Tablero", "🎯 Setup / Board modes", "🎯 Assistant / Modes d’échiquier", "🎯 Assistente / Modos de tabuleiro", "🎯 Einrichtung / Brettmodi"),
    ("🎯 Precisión en Tiempo Real", "🎯 Real-time accuracy", "🎯 Précision en temps réel", "🎯 Precisão em tempo real", "🎯 Genauigkeit in Echtzeit"),
    ("👁 Overlay", "👁 Overlay", "👁 Superposition", "👁 Sobreposição", "👁 Überlagerung"),
    ("👁 Overlay: Activado", "👁 Overlay: On", "👁 Superposition : active", "👁 Sobreposição: ativa", "👁 Überlagerung: Ein"),
    ("👁 Overlay: Desactivado", "👁 Overlay: Off", "👁 Superposition : inactive", "👁 Sobreposição: inativa", "👁 Überlagerung: Aus"),
    ("📋 Copiar FEN", "📋 Copy FEN", "📋 Copier le FEN", "📋 Copiar FEN", "📋 FEN kopieren"),
    ("📥 Pegar FEN", "📥 Paste FEN", "📥 Coller le FEN", "📥 Colar FEN", "📥 FEN einfügen"),
    ("🔄 Cambiar turno a {value0}", "🔄 Set turn to {value0}", "🔄 Donner le trait aux {value0}", "🔄 Alterar vez para {value0}", "🔄 Zugrecht auf {value0} setzen"),
    ("🔄 Sincronizar", "🔄 Synchronize", "🔄 Synchroniser", "🔄 Sincronizar", "🔄 Synchronisieren"),
    ("🔍 Escanear Pantalla", "🔍 Scan screen", "🔍 Analyser l’écran", "🔍 Analisar tela", "🔍 Bildschirm erfassen"),
    ("🗑 Vaciar casilla", "🗑 Clear square", "🗑 Vider la case", "🗑 Esvaziar casa", "🗑 Feld leeren"),
    ("🚀 Iniciar Seguimiento", "🚀 Start tracking", "🚀 Démarrer le suivi", "🚀 Iniciar acompanhamento", "🚀 Erfassung starten"),
    ("Blancas", "White", "Blancs", "Brancas", "Weiß"),
    ("Negras", "Black", "Noirs", "Pretas", "Schwarz"),
    ("Vacía", "Empty", "Vide", "Vazia", "Leer"),
    ("Rey", "King", "Roi", "Rei", "König"),
    ("Dama", "Queen", "Dame", "Dama", "Dame"),
    ("Torre", "Rook", "Tour", "Torre", "Turm"),
    ("Alfil", "Bishop", "Fou", "Bispo", "Läufer"),
    ("Caballo", "Knight", "Cavalier", "Cavalo", "Springer"),
    ("Peón", "Pawn", "Pion", "Peão", "Bauer"),
    ("Libro", "Book", "Théorie", "Livro", "Buch"),
    ("Brillante", "Brilliant", "Brillant", "Brilhante", "Brillant"),
    ("Gran jugada", "Great move", "Excellent coup", "Grande lance", "Großartiger Zug"),
    ("Excelente", "Excellent", "Excellent", "Excelente", "Ausgezeichnet"),
    ("Buena", "Good", "Bon", "Bom", "Gut"),
    ("Imprecisión", "Inaccuracy", "Imprécision", "Imprecisão", "Ungenauigkeit"),
    ("Error", "Mistake", "Erreur", "Erro", "Fehler"),
    ("Error grave", "Blunder", "Gaffe", "Erro grave", "Grober Fehler"),
    ("⚡ Recomendado{value0}", "⚡ Recommended{value0}", "⚡ Recommandé{value0}", "⚡ Recomendado{value0}", "⚡ Empfohlen{value0}"),
    ("★ Estilo · {value0}", "★ Style · {value0}", "★ Style · {value0}", "★ Estilo · {value0}", "★ Stil · {value0}"),
    ("⚙ Motor #1 · {value0}", "⚙ Engine #1 · {value0}", "⚙ Moteur #1 · {value0}", "⚙ Motor #1 · {value0}", "⚙ Engine #1 · {value0}"),
    ("Región Tablero: {width} x {height} px  (Soltar ratón para confirmar)", "Board region: {width} x {height} px  (Release mouse to confirm)", "Zone : {width} x {height} px  (Relâchez pour confirmer)", "Região: {width} x {height} px  (Solte para confirmar)", "Brettbereich: {width} x {height} px  (Zum Bestätigen loslassen)"),
    ("Selecciona la región del tablero. ESC para cancelar.", "Select the board region. ESC to cancel.", "Sélectionnez la zone de l’échiquier. Échap pour annuler.", "Selecione a região do tabuleiro. ESC para cancelar.", "Wählen Sie den Brettbereich. ESC zum Abbrechen."),
    ("Posición Inicial Estándar", "Standard starting position", "Position initiale standard", "Posição inicial padrão", "Standard-Ausgangsstellung"),
    ("Mate de la Ópera (Paul Morphy)", "Opera mate (Paul Morphy)", "Mat de l’opéra (Paul Morphy)", "Mate da Ópera (Paul Morphy)", "Opernmatt (Paul Morphy)"),
    ("Inmortal de Kasparov (vs Topalov)", "Kasparov’s immortal (vs Topalov)", "Immortelle de Kasparov (contre Topalov)", "Imortal de Kasparov (contra Topalov)", "Kasparows Unsterbliche (gegen Topalow)"),
    ("Sacrificio Clásico de Alfil en h7", "Classic bishop sacrifice on h7", "Sacrifice classique du fou en h7", "Sacrifício clássico de bispo em h7", "Klassisches Läuferopfer auf h7"),
    ("Táctica de Coronación en Final", "Endgame promotion tactic", "Tactique de promotion en finale", "Tática de promoção no final", "Umwandlungstaktik im Endspiel"),
    ("Defensa Siciliana (Variante Najdorf)", "Sicilian Defense (Najdorf)", "Défense sicilienne (Najdorf)", "Defesa siciliana (Najdorf)", "Sizilianische Verteidigung (Najdorf)"),
    ("Gambito de Dama Aceptado", "Queen’s Gambit Accepted", "Gambit dame accepté", "Gambito da dama aceito", "Angenommenes Damengambit"),
    ("Jugada teórica de apertura estándar.", "Standard theoretical opening move.", "Coup théorique d’ouverture standard.", "Lance teórico de abertura padrão.", "Theoretischer Standard-Eröffnungszug."),
    ("¡Sacrificio brillante que mantiene la ventaja ganadora!", "Brilliant sacrifice that preserves a winning advantage!", "Sacrifice brillant qui conserve l’avantage gagnant !", "Sacrifício brilhante que mantém a vantagem decisiva!", "Brillantes Opfer, das den Gewinnvorteil erhält!"),
    ("Jugada clave que encuentra el único camino ganador.", "Key move finding the only winning path.", "Coup clé trouvant la seule voie gagnante.", "Lance chave que encontra o único caminho vencedor.", "Schlüsselzug, der den einzigen Gewinnweg findet."),
    ("La jugada más precisa según el motor Stockfish.", "The most accurate move according to Stockfish.", "Le coup le plus précis selon Stockfish.", "O lance mais preciso segundo o Stockfish.", "Der präziseste Zug laut Stockfish."),
    ("Movimiento muy fuerte que mantiene casi intacta la ventaja.", "Very strong move preserving nearly all the advantage.", "Coup très fort conservant presque tout l’avantage.", "Lance muito forte que preserva quase toda a vantagem.", "Sehr starker Zug, der den Vorteil fast vollständig erhält."),
    ("Movimiento sólido con mínima pérdida de posición.", "Solid move with minimal positional loss.", "Coup solide avec une perte de position minimale.", "Lance sólido com perda mínima de posição.", "Solider Zug mit minimalem Stellungsverlust."),
    ("Movimiento dudoso que cede parte de la iniciativa.", "Dubious move giving up some initiative.", "Coup douteux qui cède une partie de l’initiative.", "Lance duvidoso que cede parte da iniciativa.", "Fragwürdiger Zug, der etwas Initiative abgibt."),
    ("Error táctico o posicional que perjudica la partida.", "Tactical or positional mistake harming the game.", "Erreur tactique ou positionnelle nuisible à la partie.", "Erro tático ou posicional que prejudica a partida.", "Taktischer oder positioneller Fehler zum Nachteil der Partie."),
    ("Fallo crítico que compromete severamente la posición.", "Critical mistake severely compromising the position.", "Erreur critique compromettant gravement la position.", "Erro crítico que compromete seriamente a posição.", "Schwerer Fehler, der die Stellung erheblich verschlechtert."),
    ("Única jugada disponible", "Only available move", "Seul coup disponible", "Único lance disponível", "Einziger verfügbarer Zug"),
    ("Derrota sutil (Declive natural y orgánico)", "Gradual loss (Natural decline)", "Défaite progressive (Déclin naturel)", "Derrota gradual (Declínio natural)", "Schleichende Niederlage (Natürlicher Rückgang)"),
    ("Derrota sutil (Fase sólida inicial: jugada {value0}/{value1})", "Gradual loss (Solid opening phase: move {value0}/{value1})", "Défaite progressive (Phase initiale solide : coup {value0}/{value1})", "Derrota gradual (Fase inicial sólida: lance {value0}/{value1})", "Schleichende Niederlage (Solide Anfangsphase: Zug {value0}/{value1})"),
    ("Error sutil inducido (No obvio · Pérdida {value0:.0f} cp)", "Simulated subtle error (Loss {value0:.0f} cp)", "Erreur subtile simulée (Perte {value0:.0f} cp)", "Erro sutil simulado (Perda {value0:.0f} cp)", "Simulierter subtiler Fehler (Verlust {value0:.0f} cp)"),
    ("Derrota sutil (Buscando error sutil sin regalar la partida · Jugada {value0})", "Gradual loss (Seeking a small error without throwing the game · Move {value0})", "Défaite progressive (Recherche d’une petite erreur sans abandonner la partie · Coup {value0})", "Derrota gradual (Buscando pequeno erro sem entregar a partida · Lance {value0})", "Schleichende Niederlage (Kleiner Fehler ohne Partieaufgabe gesucht · Zug {value0})"),
    ("Ajuste a objetivo {value0}% (Actual: {value1:.1f}%, jugada secundaria natural)", "Adjusting to target {value0}% (Current: {value1:.1f}%, natural alternative)", "Ajustement à {value0}% (Actuel : {value1:.1f}%, alternative naturelle)", "Ajustando ao alvo {value0}% (Atual: {value1:.1f}%, alternativa natural)", "Anpassung an Ziel {value0}% (Aktuell: {value1:.1f}%, natürliche Alternative)"),
    ("Mejor jugada preservada (Sin alternativa secundaria segura, Obj: {value0}%)", "Best move preserved (No safe alternative, target: {value0}%)", "Meilleur coup conservé (Aucune alternative sûre, cible : {value0}%)", "Melhor lance preservado (Sem alternativa segura, alvo: {value0}%)", "Bester Zug beibehalten (Keine sichere Alternative, Ziel: {value0}%)"),
    ("Subir precisión a {value0}% (Actual: {value1:.1f}%, mejor jugada objetiva)", "Raising accuracy to {value0}% (Current: {value1:.1f}%, best engine move)", "Hausse de précision vers {value0}% (Actuel : {value1:.1f}%, meilleur coup du moteur)", "Elevando precisão para {value0}% (Atual: {value1:.1f}%, melhor lance do motor)", "Genauigkeit auf {value0}% erhöhen (Aktuell: {value1:.1f}%, bester Enginezug)"),
    ("Objetivo cumplido ({value0:.1f}% ≈ {value1}%) · Variabilidad humana", "Target reached ({value0:.1f}% ≈ {value1}%) · Human variation", "Objectif atteint ({value0:.1f}% ≈ {value1}%) · Variabilité humaine", "Alvo atingido ({value0:.1f}% ≈ {value1}%) · Variação humana", "Ziel erreicht ({value0:.1f}% ≈ {value1}%) · Menschliche Variation"),
)

TRANSLATIONS = {
    code: {row[0]: row[index] for row in _MESSAGES}
    for index, code in enumerate(LANGUAGES)
}


def normalize_language(language: str) -> str:
    code = str(language).lower().replace("_", "-").split("-", 1)[0]
    return code if code in LANGUAGES else "es"


def set_language(language: str) -> str:
    global _language
    _language = normalize_language(language)
    return _language


def get_language() -> str:
    return _language


def tr(source: str, **values) -> str:
    translated = TRANSLATIONS[_language].get(source, source)
    if not values:
        return translated
    try:
        return translated.format(**values)
    except (KeyError, ValueError, IndexError):
        # A damaged translation must not interrupt board tracking.
        return source.format(**values)


def board_name(name: str) -> str:
    """Localize only the built-in board names; keep custom names as entered."""
    match = re.fullmatch(r"Tablero ([1-4])", name)
    return tr("Tablero {number}", number=match[1]) if match else name
