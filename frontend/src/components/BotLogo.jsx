/**
 * Iter 132 — BotLogo: modern, distinctive AI-bot mark.
 *
 * A geometric humanoid AI silhouette with:
 *   • Angular chamfered helmet (front-facing 3/4 head shape)
 *   • Glowing single visor eye (cyan → magenta gradient) suggesting a neural sensor
 *   • Neural circuit lines on the side of the helmet
 *   • Antenna node with pulsing dot
 *
 * Pure SVG — scales to any size, no image assets needed. Used in the login
 * hero, header, favicon, and loading screen.
 *
 * Usage:
 *   <BotLogo size={80} />            // login hero
 *   <BotLogo size={40} glow />       // header
 *   <BotLogo size={20} minimal />    // favicon / dense UI
 */
import React, { useId } from 'react';

const BotLogo = ({ size = 40, glow = false, minimal = false, className = '', dataTestId = 'bot-logo' }) => {
  const id = useId();
  const px = `${size}px`;
  return (
    <div
      data-testid={dataTestId}
      className={`inline-flex items-center justify-center ${className}`}
      style={{ width: px, height: px }}
    >
      <svg
        viewBox="0 0 64 64"
        width={size}
        height={size}
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="AI Bot logo"
        style={glow ? { filter: `drop-shadow(0 0 ${size / 6}px rgba(56, 189, 248, 0.55))` } : undefined}
      >
        <defs>
          {/* Chrome / helmet body gradient */}
          <linearGradient id={`bg-${id}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="#1e293b" />
            <stop offset="60%"  stopColor="#0f172a" />
            <stop offset="100%" stopColor="#020617" />
          </linearGradient>
          {/* Edge highlight */}
          <linearGradient id={`edge-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%"   stopColor="#38bdf8" />
            <stop offset="60%"  stopColor="#22d3ee" />
            <stop offset="100%" stopColor="#a855f7" />
          </linearGradient>
          {/* Visor / eye glow */}
          <linearGradient id={`eye-${id}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%"   stopColor="#22d3ee" />
            <stop offset="50%"  stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#a855f7" />
          </linearGradient>
          <radialGradient id={`spark-${id}`} cx="50%" cy="50%" r="50%">
            <stop offset="0%"  stopColor="#f0abfc" stopOpacity="0.9" />
            <stop offset="60%" stopColor="#38bdf8" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Antenna */}
        {!minimal && (
          <>
            <line x1="32" y1="4" x2="32" y2="10" stroke={`url(#edge-${id})`} strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="32" cy="3.2" r="2.2" fill={`url(#eye-${id})`}>
              <animate attributeName="r" values="2;2.6;2" dur="2.2s" repeatCount="indefinite" />
            </circle>
          </>
        )}

        {/* Helmet — chamfered hexagonal front */}
        <path
          d="M14 20 L20 12 L44 12 L50 20 L50 46 L44 54 L20 54 L14 46 Z"
          fill={`url(#bg-${id})`}
          stroke={`url(#edge-${id})`}
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* Inner face plate cutout */}
        <path
          d="M20 22 L24 18 L40 18 L44 22 L44 40 L40 44 L24 44 L20 40 Z"
          fill="#020617"
          stroke={`url(#edge-${id})`}
          strokeWidth="0.6"
          strokeOpacity="0.4"
          strokeLinejoin="round"
        />

        {/* Visor — glowing eye slit */}
        <rect x="24" y="26" width="16" height="6" rx="1.2" fill={`url(#eye-${id})`} opacity="0.95" />
        {/* Highlight streak */}
        <rect x="25.5" y="27.2" width="6" height="0.9" fill="#e0f2fe" opacity="0.9" />
        {/* Spark glow behind eye */}
        <circle cx="32" cy="29" r="7" fill={`url(#spark-${id})`} />

        {/* Small "cheek" vents / detail lines (kept out of minimal mode) */}
        {!minimal && (
          <>
            <line x1="26" y1="37" x2="30" y2="37" stroke={`url(#edge-${id})`} strokeWidth="0.9" strokeLinecap="round" opacity="0.75" />
            <line x1="34" y1="37" x2="38" y2="37" stroke={`url(#edge-${id})`} strokeWidth="0.9" strokeLinecap="round" opacity="0.75" />
            {/* Circuit trace on left cheek */}
            <path
              d="M9 30 L13 30 L13 34 L11 34"
              fill="none"
              stroke={`url(#edge-${id})`}
              strokeWidth="0.9"
              strokeLinecap="round"
              opacity="0.6"
            />
            <circle cx="9" cy="30" r="1.2" fill={`url(#eye-${id})`} opacity="0.8" />
            {/* Circuit trace on right cheek */}
            <path
              d="M55 30 L51 30 L51 34 L53 34"
              fill="none"
              stroke={`url(#edge-${id})`}
              strokeWidth="0.9"
              strokeLinecap="round"
              opacity="0.6"
            />
            <circle cx="55" cy="30" r="1.2" fill={`url(#eye-${id})`} opacity="0.8" />
          </>
        )}

        {/* Chin / mouth grille */}
        <line x1="28" y1="49"  x2="36" y2="49"  stroke={`url(#edge-${id})`} strokeWidth="1" strokeLinecap="round" opacity="0.7" />
        <line x1="30" y1="51.5" x2="34" y2="51.5" stroke={`url(#edge-${id})`} strokeWidth="0.8" strokeLinecap="round" opacity="0.5" />
      </svg>
    </div>
  );
};

export default BotLogo;
export { BotLogo };
