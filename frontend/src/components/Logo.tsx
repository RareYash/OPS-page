import React from 'react';

interface LogoProps {
  size?: number;
  className?: string;
  style?: React.CSSProperties;
  showShadow?: boolean;
}

export const Logo: React.FC<LogoProps> = ({
  size = 36,
  className,
  style,
  showShadow = true,
}) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle', flexShrink: 0, ...style }}
    >
      {/* 1. Base Drop Shadow */}
      {showShadow && (
        <ellipse
          cx="50"
          cy="92"
          rx="32"
          ry="3"
          fill="#e7dfd5"
          opacity="0.75"
        />
      )}

      {/* 2. Outer Industrial Cog / Gear (Warm Stone Espresso) */}
      <g fill="#292524">
        {/* 8 Gear Teeth */}
        {/* Tooth 0 deg (Top) */}
        <rect x="42" y="10" width="16" height="14" rx="4" />
        {/* Tooth 180 deg (Bottom) */}
        <rect x="42" y="70" width="16" height="14" rx="4" />
        {/* Tooth 90 deg (Right) */}
        <rect x="70" y="40" width="14" height="16" rx="4" />
        {/* Tooth 270 deg (Left) */}
        <rect x="10" y="40" width="14" height="16" rx="4" />

        {/* Diagonal Teeth (45, 135, 225, 315 deg) */}
        <rect x="42" y="10" width="16" height="14" rx="4" transform="rotate(45 50 48)" />
        <rect x="42" y="10" width="16" height="14" rx="4" transform="rotate(135 50 48)" />
        <rect x="42" y="10" width="16" height="14" rx="4" transform="rotate(225 50 48)" />
        <rect x="42" y="10" width="16" height="14" rx="4" transform="rotate(315 50 48)" />

        {/* Outer Circular Ring Body */}
        <circle cx="50" cy="48" r="32" />
      </g>

      {/* 3. Inner White Circular Cavity */}
      <circle cx="50" cy="48" r="23.5" fill="#ffffff" />

      {/* 4. Operator Figure in Warm Terracotta / Amber */}
      <g fill="#ea580c">
        {/* Head */}
        <circle cx="50" cy="40.5" r="7.5" />

        {/* Clip path for torso inside inner circle */}
        <mask id="inner-circle-mask">
          <circle cx="50" cy="48" r="23.5" fill="#ffffff" />
        </mask>

        <g mask="url(#inner-circle-mask)">
          {/* Torso & Shoulders */}
          <path
            d="M33 66 C33 55 41 51 50 51 C59 51 67 55 67 66 Z"
            fill="#ea580c"
          />

          {/* White Shirt Collar Cutout */}
          <polygon
            points="46,51 50,56 47.5,51"
            fill="#ffffff"
          />
          <polygon
            points="54,51 50,56 52.5,51"
            fill="#ffffff"
          />
          <polygon
            points="45,51 50,57 47,58"
            fill="#ffffff"
          />
          <polygon
            points="55,51 50,57 53,58"
            fill="#ffffff"
          />

          {/* Corporate Tie */}
          <polygon
            points="49.2,54 50.8,54 51.5,59 50,62 48.5,59"
            fill="#ea580c"
          />
        </g>
      </g>
    </svg>
  );
};
