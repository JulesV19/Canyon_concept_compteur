import QtQuick

// Toucher de CarPlay, tolérant comme sur une voiture : un appui long compte encore, et le doigt peut glisser un peu
// tant qu'il se relève sur la cible. Par défaut, TapHandler abandonne au-delà de 0,8 s ou de quelques pixels, ce qui
// arrive vite sur un petit écran tactile, à vélo.
TapHandler {
    gesturePolicy: TapHandler.ReleaseWithinBounds
    longPressThreshold: 0
}
