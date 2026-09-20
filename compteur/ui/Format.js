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

// Avec un signe + devant une valeur positive (le moins vient de number)
function signed(value, decimals) {
    const text = number(value, decimals)
    return value !== null && value !== undefined && Number(value.toFixed(decimals || 0)) > 0 ? "+" + text : text
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

// Durée approchée : « 42 min », « 5 h 09 »
function span(seconds) {
    if (seconds === null || seconds === undefined)
        return "--"
    const m = Math.floor(seconds / 60)
    return m < 60 ? m + " min" : Math.floor(m / 60) + " h " + String(m % 60).padStart(2, "0")
}

// Temps d'un segment : m:ss, ou h:mm:ss au-delà d'une heure
function clock(seconds) {
    if (seconds === null || seconds === undefined)
        return "--"
    const s = Math.round(seconds)
    return s >= 3600 ? duration(s) : Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0")
}

const MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                "novembre", "décembre"]

// Jour et mois d'une date AAAA-MM-JJ : « 3 juin »
function dayMonth(iso) {
    const parts = (iso || "").split("-")
    if (parts.length !== 3)
        return ""
    return Number(parts[2]) + " " + MONTHS[Number(parts[1]) - 1]
}

// Écart signé, avec un vrai signe moins : « −7 » (secondes) sous la minute, « +1:02 » au-delà
function gap(seconds) {
    if (seconds === null || seconds === undefined)
        return "--"
    const s = Math.round(seconds)
    return (s < 0 ? "−" : s > 0 ? "+" : "") + (Math.abs(s) < 60 ? String(Math.abs(s)) : clock(Math.abs(s)))
}
