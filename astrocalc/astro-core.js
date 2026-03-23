/**
 * astro-core.js - High-Precision Astronomical Algorithms
 * Optimized for Web with standard Julian Date calculation.
 */

const DEG2RAD = Math.PI / 180.0;
const RAD2DEG = 180.0 / Math.PI;

export const AstroUtils = {
    /**
     * Calculates days since J2000.0 epoch using standard JD formula.
     * This avoids platform-specific epoch issues.
     */
    getDaysSinceJ2000(date) {
        // date is a JS Date object. We extract components in UTC.
        let y = date.getUTCFullYear();
        let m = date.getUTCMonth() + 1;
        let d = date.getUTCDate();
        
        if (m <= 2) {
            y -= 1;
            m += 12;
        }
        
        const a = Math.floor(y / 100);
        const b = 2 - a + Math.floor(a / 4);
        
        // JD at 0h UTC of the given date
        const jd = Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + d + b - 1524.5;
        
        // Astronomical JD epoch for J2000.0 is 2451545.0
        return jd - 2451545.0;
    },

    calculateRefraction(trueElevDeg, refractionFactor) {
        if (refractionFactor === 0.0) return 0.0;
        if (trueElevDeg > 89.8915 || trueElevDeg < -5.0015) return 0.0;
        const arg = (trueElevDeg + 10.3 / (trueElevDeg + 5.11)) * DEG2RAD;
        return 1.02 / 60.0 / Math.tan(arg) * refractionFactor;
    }
};

export class SolarCalculator {
    static generateData(lat, lon, tz, date, refractionFactor) {
        const angles = [];
        const distances = [];
        const labels = [];
        
        const latRad = lat * DEG2RAD;
        const sinLat = Math.sin(latRad);
        const cosLat = Math.cos(latRad);
        
        const baseDays = AstroUtils.getDaysSinceJ2000(date);
        
        // Pre-compute obliquity (changes very slowly)
        const obliquityDeg = 23.439291111 - 3.560347e-7 * baseDays;
        const obliquitySin = Math.sin(obliquityDeg * DEG2RAD);
        const obliquityCos = Math.cos(obliquityDeg * DEG2RAD);
        const eclipticC1 = 1.914602;
        const eclipticC2 = 0.019993;
        const tstOffset = 4.0 * lon - 60.0 * tz;
        const eccentricity = 0.016708634;

        for (let i = 0; i < 1440; i += 2) { // 2-minute steps for balance
            const days = baseDays + (i / 60.0 - tz) / 24.0;
            let meanAnomalyDeg = (357.52772 + 0.985600282 * days) % 360;
            if (meanAnomalyDeg < 0) meanAnomalyDeg += 360;
            let meanLonDeg = (280.46645 + 0.98564736 * days) % 360;
            if (meanLonDeg < 0) meanLonDeg += 360;
            
            const meanAnomRad = meanAnomalyDeg * DEG2RAD;
            const eqCenterDeg = eclipticC1 * Math.sin(meanAnomRad) + eclipticC2 * Math.sin(2 * meanAnomRad) + 0.000289 * Math.sin(3 * meanAnomRad);
            
            let eclLonDeg = (meanLonDeg + eqCenterDeg) % 360;
            if (eclLonDeg < 0) eclLonDeg += 360;
            const eclLonRad = eclLonDeg * DEG2RAD;
            
            const sinDec = Math.max(-1, Math.min(1, obliquitySin * Math.sin(eclLonRad)));
            const cosDec = Math.sqrt(1 - sinDec * sinDec);
            
            const meanTimeHrs = meanLonDeg / 15.0;
            let raHrs = Math.atan2(obliquityCos * Math.sin(eclLonRad), Math.cos(eclLonRad)) * RAD2DEG / 15.0;
            if (raHrs < 0) raHrs += 24.0;
            
            const deltaRa = raHrs - meanTimeHrs;
            if (deltaRa > 12.0) raHrs -= 24.0;
            else if (deltaRa < -12.0) raHrs += 24.0;
            
            const eqTimeMin = (meanTimeHrs - raHrs) * 60.0;
            const hourAngleRad = ((i + eqTimeMin + tstOffset) / 4.0 - 180.0) * DEG2RAD;
            
            const sinElev = Math.max(-1, Math.min(1, sinLat * sinDec + cosLat * cosDec * Math.cos(hourAngleRad)));
            const geoElevDeg = Math.asin(sinElev) * RAD2DEG;
            const topoElevDeg = geoElevDeg - 0.00244 * Math.sqrt(1 - sinElev * sinElev);
            
            angles.push(topoElevDeg + AstroUtils.calculateRefraction(topoElevDeg, refractionFactor));
            
            const distEmbAu = (1.0 - eccentricity * eccentricity) / (1.0 + eccentricity * Math.cos(meanAnomRad + eqCenterDeg * DEG2RAD));
            distances.push(149597870.7 * distEmbAu);
            labels.push(`${Math.floor(i/60).toString().padStart(2,'0')}:${(i%60).toString().padStart(2,'0')}`);
        }
        return { angles, distances, labels };
    }
}

export class LunarCalculator {
    static getPhaseDescription(phaseFraction, elongationDeg) {
        const e = (elongationDeg % 360 + 360) % 360;
        let desc = "";
        if (e < 5 || e > 355) desc = "New Moon";
        else if (e < 85) desc = "Waxing Crescent";
        else if (e < 95) desc = "First Quarter";
        else if (e < 175) desc = "Waxing Gibbous";
        else if (e < 185) desc = "Full Moon";
        else if (e < 265) desc = "Waning Gibbous";
        else if (e < 275) desc = "Last Quarter";
        else desc = "Waning Crescent";
        return `${desc} (${(phaseFraction * 100).toFixed(1)}%)`;
    }

    static generateData(lat, lon, tz, date, refractionFactor) {
        const angles = [];
        const distances = [];
        const phases = [];
        const labels = [];
        
        const latRad = lat * DEG2RAD;
        const sinLat = Math.sin(latRad);
        const cosLat = Math.cos(latRad);
        const baseDays = AstroUtils.getDaysSinceJ2000(date);
        
        const earthFlattening = 1.0 / 298.257223563;
        const phiPrime = Math.atan((1 - earthFlattening) * Math.tan(latRad));
        const rhoSinPhiPrime = (1 - earthFlattening) * Math.sin(phiPrime);
        const rhoCosPhiPrime = Math.cos(phiPrime);

        // Pre-compute solar parameters for phase calculation
        const baseCenturies = baseDays / 36525.0;
        const sunEqC1 = 1.914602 - 0.004817 * baseCenturies;
        const sunEqC2 = 0.019993 - 0.000101 * baseCenturies;
        const obliquityRad = (23.439291111 - 0.013004167 * baseCenturies) * DEG2RAD;
        const cosObl = Math.cos(obliquityRad);
        const sinObl = Math.sin(obliquityRad);

        for (let i = 0; i < 1440; i += 4) { // 4-minute steps
            const localDays = baseDays + (i / 60.0 - tz) / 24.0;
            const T = localDays / 36525.0;
            const T2 = T * T;
            const T3 = T2 * T;

            const moonMeanLon = 218.3164477 + 481267.88123421 * T - 0.0015786 * T2;
            const meanElong = 297.8501921 + 445267.1114034 * T - 0.0018819 * T2;
            const sunMeanAnom = 357.5291092 + 35999.0502909 * T;
            const moonMeanAnom = 134.9633964 + 477198.8675055 * T + 0.0087414 * T2;
            const moonArgLat = 93.2720950 + 483202.0175233 * T - 0.0036539 * T2;

            const D = meanElong * DEG2RAD;
            const M = sunMeanAnom * DEG2RAD;
            const Mm = moonMeanAnom * DEG2RAD;
            const F = moonArgLat * DEG2RAD;

            // Meeus's truncated moon position
            const eclLon = moonMeanLon
                + 6.2888 * Math.sin(Mm)
                + 1.2740 * Math.sin(2 * D - Mm)
                + 0.6583 * Math.sin(2 * D)
                + 0.2136 * Math.sin(2 * D - M)
                - 0.1856 * Math.sin(M)
                - 0.1143 * Math.sin(2 * F)
                - 0.0588 * Math.sin(2 * D - 2 * Mm);

            const eclLat = 5.1282 * Math.sin(F)
                + 0.2806 * Math.sin(Mm + F)
                + 0.2777 * Math.sin(Mm - F)
                + 0.1732 * Math.sin(2 * D - F);

            const dist = 385000.6 - 20905.0 * Math.cos(Mm) - 3699.0 * Math.cos(2 * D - Mm) - 2956.0 * Math.cos(2 * D);
            
            const parallaxSin = 6378.137 / dist;
            const lambdaMoon = eclLon * DEG2RAD;
            const betaMoon = eclLat * DEG2RAD;

            // Phase and Elongation
            let sunMeanLon = (280.46646 + 36000.76983 * T) % 360;
            const sunEqCenter = sunEqC1 * Math.sin(M) + sunEqC2 * Math.sin(2 * M);
            const sunTrueLon = (sunMeanLon + sunEqCenter) * DEG2RAD;
            const cosElong = Math.cos(betaMoon) * Math.cos(lambdaMoon - sunTrueLon);
            const illuFraction = (1.0 - cosElong) / 2.0;
            let elonDeg = (eclLon - (sunMeanLon + sunEqCenter)) % 360;

            // Topocentric correction
            const raRad = Math.atan2(Math.sin(lambdaMoon) * cosObl - Math.tan(betaMoon) * sinObl, Math.cos(lambdaMoon));
            const decRad = Math.asin(Math.sin(betaMoon) * cosObl + Math.cos(betaMoon) * sinObl * Math.sin(lambdaMoon));

            let gmst = (280.4606 + 360.985647 * localDays) % 360;
            const haRad = (gmst + lon) * DEG2RAD - raRad;
            const cosDec = Math.cos(decRad);
            
            const A = cosDec * Math.sin(haRad);
            const B = cosDec * Math.cos(haRad) - rhoCosPhiPrime * parallaxSin;
            const C = Math.sin(decRad) - rhoSinPhiPrime * parallaxSin;

            const topDecRad = Math.atan2(C, Math.sqrt(A * A + B * B));
            const sinElev = Math.max(-1, Math.min(1, sinLat * Math.sin(topDecRad) + cosLat * Math.cos(topDecRad) * Math.cos(Math.atan2(A, B))));
            const trueElevDeg = Math.asin(sinElev) * RAD2DEG;
            
            angles.push(trueElevDeg + AstroUtils.calculateRefraction(trueElevDeg, refractionFactor));
            distances.push(Math.sqrt(A * A + B * B + C * C) * dist);
            phases.push(this.getPhaseDescription(illuFraction, elonDeg));
            labels.push(`${Math.floor(i/60).toString().padStart(2,'0')}:${(i%60).toString().padStart(2,'0')}`);
        }
        return { angles, distances, phases, labels };
    }
}
