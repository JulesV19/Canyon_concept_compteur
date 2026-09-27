.pragma library

// Calculs de la carte, sans état

// Écart d'angle le plus court, en degrés
function turn(from, to) {
    return ((to - from) % 360 + 540) % 360 - 180
}

// Le parcours en tronçons de 100 points, chacun avec sa position le long du tracé. Deux tronçons voisins partagent un
// point : leurs bouts arrondis se recouvrent, et le trait paraît continu.
function routeChunks(route) {
    const chunks = []
    let start = 0
    for (let i = 0; i + 1 < route.length; i += 100) {
        const points = route.slice(i, i + 101)
        let length = 0
        for (let k = 1; k < points.length; k++)
            length += Math.hypot(points[k].x - points[k - 1].x, points[k].y - points[k - 1].y)
        chunks.push({ points: points, start: start, length: length })
        start += length
    }
    return chunks
}
