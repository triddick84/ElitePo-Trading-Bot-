/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    	extend: {
    		borderRadius: {
    			lg: 'var(--radius)',
    			md: 'calc(var(--radius) - 2px)',
    			sm: 'calc(var(--radius) - 4px)'
    		},
    		colors: {
    			background: 'hsl(var(--background))',
    			foreground: 'hsl(var(--foreground))',
    			card: {
    				DEFAULT: 'hsl(var(--card))',
    				foreground: 'hsl(var(--card-foreground))'
    			},
    			popover: {
    				DEFAULT: 'hsl(var(--popover))',
    				foreground: 'hsl(var(--popover-foreground))'
    			},
    			primary: {
    				DEFAULT: 'hsl(var(--primary))',
    				foreground: 'hsl(var(--primary-foreground))'
    			},
    			secondary: {
    				DEFAULT: 'hsl(var(--secondary))',
    				foreground: 'hsl(var(--secondary-foreground))'
    			},
    			muted: {
    				DEFAULT: 'hsl(var(--muted))',
    				foreground: 'hsl(var(--muted-foreground))'
    			},
    			accent: {
    				DEFAULT: 'hsl(var(--accent))',
    				foreground: 'hsl(var(--accent-foreground))'
    			},
    			destructive: {
    				DEFAULT: 'hsl(var(--destructive))',
    				foreground: 'hsl(var(--destructive-foreground))'
    			},
    			border: 'hsl(var(--border))',
    			input: 'hsl(var(--input))',
    			ring: 'hsl(var(--ring))',
    			chart: {
    				'1': 'hsl(var(--chart-1))',
    				'2': 'hsl(var(--chart-2))',
    				'3': 'hsl(var(--chart-3))',
    				'4': 'hsl(var(--chart-4))',
    				'5': 'hsl(var(--chart-5))'
    			},
    			// Iter 85 — AI Trading Synthwave palette.
    			// Remap `purple` (the "AI slop" accent) → neon cyan/electric-blue.
    			// All existing JSX using `bg-purple-500`, `text-purple-400`, etc.
    			// now renders as the new theme without touching any JSX.
    			purple: {
    				50:  '#E6FDFF',
    				100: '#B8F8FF',
    				200: '#7FEEFF',
    				300: '#3FE1FF',
    				400: '#00D7FF',
    				500: '#00C4EE',
    				600: '#00A0CC',
    				700: '#0080AB',
    				800: '#006180',
    				900: '#00435A',
    				950: '#002834'
    			},
    			// Deep navy scale for the app base & surfaces.
    			navy: {
    				50:  '#E2E8FF',
    				100: '#BAC3F0',
    				200: '#8890D6',
    				300: '#5A63BC',
    				400: '#333DA1',
    				500: '#1F2A78',
    				600: '#131C55',
    				700: '#0B132B',
    				800: '#050814',
    				900: '#02040A'
    			}
    		},
    		boxShadow: {
    			// Iter 85 — reusable neon glow presets
    			'neon-cyan':    '0 0 20px rgba(0, 240, 255, 0.35)',
    			'neon-cyan-lg': '0 0 30px rgba(0, 240, 255, 0.55)',
    			'neon-blue':    '0 0 20px rgba(46, 139, 255, 0.35)',
    			'neon-green':   '0 0 18px rgba(0, 230, 118, 0.40)',
    			'neon-red':     '0 0 18px rgba(255, 23, 68, 0.35)',
    			'neon-amber':   '0 0 18px rgba(255, 196, 0, 0.35)'
    		},
    		fontFamily: {
    			mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'ui-monospace',
    				'SFMono-Regular', 'Menlo', 'Consolas', 'monospace']
    		},
    		keyframes: {
    			'accordion-down': {
    				from: {
    					height: '0'
    				},
    				to: {
    					height: 'var(--radix-accordion-content-height)'
    				}
    			},
    			'accordion-up': {
    				from: {
    					height: 'var(--radix-accordion-content-height)'
    				},
    				to: {
    					height: '0'
    				}
    			},
    			// Iter 85 — pulsing neon glow for live indicators
    			'pulse-neon': {
    				'0%, 100%': { boxShadow: '0 0 8px rgba(0, 240, 255, 0.6), 0 0 16px rgba(0, 240, 255, 0.3)' },
    				'50%':      { boxShadow: '0 0 14px rgba(0, 240, 255, 0.95), 0 0 28px rgba(0, 240, 255, 0.55)' }
    			}
    		},
    		animation: {
    			'accordion-down': 'accordion-down 0.2s ease-out',
    			'accordion-up': 'accordion-up 0.2s ease-out',
    			'pulse-neon': 'pulse-neon 2s ease-in-out infinite'
    		}
    	}
  },
  plugins: [require("tailwindcss-animate")],
};
