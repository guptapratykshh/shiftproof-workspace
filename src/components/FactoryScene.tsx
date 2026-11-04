import { usePreferences } from "../lib/preferences";

/** Illustration pigments stay lavender in both themes; surrounding UI uses theme tokens. */
export function FactoryScene() {
  const { t } = usePreferences();
  return (
    <svg
      className="factory-scene"
      viewBox="0 0 480 310"
      role="img"
      aria-label={t(
        "An isometric purple production line with packages awaiting inspection",
        "निरीक्षण की प्रतीक्षा कर रहे पैकेजों के साथ बैंगनी उत्पादन लाइन",
      )}
    >
      <defs>
        <linearGradient id="platform" x1="0%" y1="0%" x2="70%" y2="100%">
          <stop stopColor="#c2a8ed" />
          <stop offset=".6" stopColor="#b098df" />
          <stop offset="1" stopColor="#a18bc9" />
        </linearGradient>
        <linearGradient id="platform-edge" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop stopColor="#ad96c4" />
          <stop offset="1" stopColor="#796586" />
        </linearGradient>
        <linearGradient id="machine-face" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop stopColor="#a18ab9" />
          <stop offset="1" stopColor="#7e6599" />
        </linearGradient>
        <linearGradient id="package-face" x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="#ac84de" />
          <stop offset="1" stopColor="#8c61c3" />
        </linearGradient>
        <filter
          id="factory-shadow"
          x="-30%"
          y="-30%"
          width="160%"
          height="180%"
        >
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>
      <ellipse
        cx="247"
        cy="275"
        rx="146"
        ry="18"
        fill="#171321"
        opacity=".2"
        filter="url(#factory-shadow)"
      />
      <path d="m76 193 90-82 244 82-90 82z" fill="url(#platform)" />
      <path d="m76 193 244 82v19L76 207z" fill="url(#platform-edge)" />
      <path d="m320 275 90-82v14l-90 87z" fill="#766288" />
      <path
        d="m80 195 240 81 86-79"
        fill="none"
        stroke="#c7b1dc"
        strokeWidth="3"
        opacity=".6"
      />
      <path
        d="m80 204 240 82 85-82"
        fill="none"
        stroke="#9e87b2"
        strokeWidth="4"
        opacity=".6"
      />
      <path d="m131 169 65-34 147 54-33 42z" fill="#9c86b5" />
      <path d="m131 169 179 62v10l-179-62z" fill="#7b688e" />
      <path d="m310 231 33-42v10l-33 42z" fill="#695775" />
      <path d="m141 165 49-24 140 51-27 31z" fill="#776284" />
      {Array.from({ length: 12 }, (_, index) => (
        <g
          key={index}
          transform={`translate(${143 + index * 13},${166 + index * 4.75})`}
        >
          <path
            d="M0 0 24-25"
            stroke="#675678"
            strokeWidth="8"
            strokeLinecap="round"
          />
          <path
            d="M0-3 24-28"
            stroke="#b09ac4"
            strokeWidth="6"
            strokeLinecap="round"
          />
        </g>
      ))}
      <path d="m177 75 45-16 39 11-44 18z" fill="#b293d0" />
      <path d="m177 75 40 13v82l-40-15z" fill="url(#machine-face)" />
      <path d="m217 88 44-18v82l-44 18z" fill="#83659f" />
      <path d="m184 91 28 9v26l-28-9z" fill="#342642" />
      <path d="m189 98 17 6v12l-17-6z" fill="#b99ae3" />
      <path d="m151 126 25-11 20 7-26 12z" fill="#af96c6" />
      <path d="m151 126 19 8v30l-19-7z" fill="#89729e" />
      <path d="m170 134 26-12v29l-26 13z" fill="#79618e" />
      <path d="m154 146 12 4v6l-12-4z" fill="#bba4d2" />
      <path d="m202 143 27-13 28 9-28 15z" fill="#b38ae5" />
      <path d="m202 143 27 11v33l-27-10z" fill="url(#package-face)" />
      <path d="m229 154 28-15v32l-28 16z" fill="#966ac9" />
      <path d="m218 137 29 11" stroke="#c5a4eb" strokeWidth="2" opacity=".65" />
      <path d="m293 91 14-8 43 12-15 10z" fill="#a894b9" />
      <path d="m293 91 42 14v10l-42-14z" fill="#82708f" />
      <path d="m335 105 15-10v10l-15 10z" fill="#73617f" />
      <path d="m318 107 8 3v66l-8-3z" fill="#8b769a" />
      <path d="m326 110 6-4v64l-6 6z" fill="#6c577b" />
      <ellipse
        cx="301"
        cy="122"
        rx="17"
        ry="16"
        fill="none"
        stroke="#70548f"
        strokeWidth="7"
      />
      <ellipse
        cx="298"
        cy="120"
        rx="17"
        ry="16"
        fill="none"
        stroke="#b38ae6"
        strokeWidth="6"
      />
      <path d="m273 173 25-14 28 9-27 15z" fill="#ab96c1" />
      <path d="m273 173 26 10v31l-26-10z" fill="#8b769f" />
      <path d="m299 183 27-15v31l-27 15z" fill="#79618d" />
      <path d="m285 165 28 11" stroke="#c5afd7" strokeWidth="2" opacity=".7" />
    </svg>
  );
}
