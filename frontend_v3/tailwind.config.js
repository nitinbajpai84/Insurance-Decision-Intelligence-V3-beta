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
          violet: "#0F6B6B",
          violetDark: "#0B5555",
          teal: "#0F6B6B",
          amber: "#A35F00",
          rose: "#B4436C",
          ink: "#052A52",
          inkDark: "#041F3D"
        }
      },
      backgroundImage: {
        "v3-hero": "linear-gradient(#052A52, #052A52)",
        "v3-sidebar": "linear-gradient(#052A52, #052A52)"
      },
      boxShadow: {
        card: "0 1px 2px rgba(5,42,82,0.04), 0 1px 0 rgba(5,42,82,0.06)",
        glow: "0 0 0 1px rgba(5,42,82,0.09)"
      }
    }
  },
  plugins: []
};
