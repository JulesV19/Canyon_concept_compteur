.pragma library

// Nombre à la française (virgule, vrai signe moins) ; "--" si la valeur est absente.
function number(value, decimals) {
    if (value === null || value === undefined || isNaN(value))
        return "--"
    let text = value.toFixed(decimals || 0)
    if (/^-0(\.0*)?$/.test(text))
        text = text.slice(1)  // pas de « −0 »
    return text.replace(".", ",").replace("-", "−")
}

// Durée en h:mm:ss
function duration(seconds) {
    if (seconds === null || seconds === undefined)
        return "--"
    const s = Math.floor(seconds)
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    return h + ":" + String(m).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0")
}
