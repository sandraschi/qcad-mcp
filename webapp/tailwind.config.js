/** @type {import('tailwindcss').Config} */
export default {
	content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
	theme: {
		extend: {
			// Vendored Apps hub token aliases (APPS_PAGE_STANDARD.md). Maps the
			// canonical card/muted tokens onto qcad's dark palette.
			colors: {
				background: "#18181c",
				foreground: "#f1f5f9",
				card: "#1e1e26",
				border: "#3f3f46",
				muted: "#27272a",
				"muted-foreground": "#8b8b93",
				"gh-green": "#22c55e",
			},
		},
	},
	plugins: [],
};
