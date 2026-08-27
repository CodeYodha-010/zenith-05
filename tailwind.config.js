/** Tailwind config for Zenith Export AI
 *  Mirrors the previous inline CDN config in base.html exactly.
 *  Used by the Tailwind standalone CLI to precompile utilities:
 *    ./tailwindcss.exe -i static/rag_app/css/tailwind.in.css -o static/rag_app/css/tailwind.css --minify
 */
module.exports = {
  darkMode: 'class',
  content: [
    './rag_app/templates/**/*.html',
    './rag_app/static/rag_app/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        'z-bg':           '#111111',
        'z-surface':      '#141414',
        'z-surface-2':    '#1a1a1a',
        'z-surface-3':    '#1f1f1f',
        'z-border':       '#262626',
        'z-border-hover': '#333333',
        'z-text-primary': '#e5e5e5',
        'z-text-secondary':'#8c8c8c',
        'z-text-muted':   '#525252',
        'z-accent':       '#00d4aa',
        'z-accent-hover': '#14e8bb',
        'z-accent-dim':   'rgba(0, 212, 170, 0.12)',
        'z-accent-border':'rgba(0, 212, 170, 0.35)',
        'z-teal':         '#00d4aa',
        'z-teal-dim':     'rgba(0, 212, 170, 0.12)',
        'z-teal-border':  'rgba(0, 212, 170, 0.35)',
        'z-warning':      '#f59e0b',
        'z-warning-dim':  'rgba(245, 158, 11, 0.12)',
        'z-warning-border':'rgba(245, 158, 11, 0.35)',
        'z-error':        '#ef4444',
        'z-error-dim':    'rgba(239, 68, 68, 0.12)',
      },
      fontFamily: {
        display: ['"DM Serif Display"', 'Georgia', 'serif'],
        body:    ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono:    ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
      animation: {
        'fade-in':   'z-fade-in 0.5s ease-out',
        'scale-in':  'z-scale-in 0.3s ease-out',
        'slide-in':  'z-slide-in 0.35s ease-out',
        'slide-down':'z-slide-down 0.25s ease-out',
      },
    },
  },
};