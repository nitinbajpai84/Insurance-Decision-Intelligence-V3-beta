/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./services/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        // Deliberately distinct from V2's indigo/gold "brand" palette — violet
        // signals "this is the beta, not the production Meridian site."
        v3: {
          violet: "#7C3AED",
          violetDark: "#5B21B6",
          teal: "#0D9488",
          amber: "#D97706",
          rose: "#DC2626",
          ink: "#1E1B2E",
          inkDark: "#141225"
        }
      },
      backgroundImage: {
        "v3-hero": "linear-gradient(135deg, #1E1B2E 0%, #2C2450 55%, #3B2A6B 100%)",
        "v3-sidebar": "linear-gradient(180deg, #1E1B2E 0%, #16132A 100%)"
      },
      boxShadow: {
        card: "0 1px 2px rgba(30,27,46,0.04), 0 8px 24px rgba(30,27,46,0.08)",
        glow: "0 8px 30px rgba(124,58,237,0.25)"
      }
    }
  },
  plugins: []
};
