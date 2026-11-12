// DigiHub deployment configuration.  The Valve payload is served from this
// same repository through jsDelivr, pinned to the commit that contains
// valve-parts/.  The `main` branch keeps the local `./valve-parts/` config.
window.CS16_CONFIG = {
    partsBaseUrl: 'https://cdn.jsdelivr.net/gh/TecTroncoso/CounterStrikeLocal@8d584c0844e1d967bb8d70c2c8f31bd8682309b0/valve-parts/',
};
