# qcad-mcp Webapp

Vite + React 19 dashboard for QCAD MCP. Fleet ports **11967** (frontend) proxying to **11966** (backend).

## Pages

| Route | Page | Description |
|:---|:---|:---|
| `/` | Dashboard | ezdxf status, file counts, quick action cards |
| `/depot` | Depot | DXF file browser with create/upload/rename/delete, SVG preview |
| `/viewer` | Viewer | Upload DXF → SVG preview with per-layer toggle |
| `/extrude` | Extrude | Configure wall height/thickness → generate STL |
| `/analyse` | Analyse | Room detection, area calculation summary |
| `/models` | Models | Uploads vs Outputs file listings with download |
| `/logs` | Logs | Live SSE log stream with filter/export |
| `/settings` | Settings | Extrusion defaults, Ollama config, QCAD Pro path |
| `/help` | Help | QCAD reference: intro, ezdxf, tools, formats, links |

## Stack

| Layer | Tech |
|:---|:---|
| **Framework** | React 19, React Router 7 |
| **Build** | Vite 5 |
| **Styling** | Tailwind CSS 3.4 |
| **Animation** | Framer Motion 11 |
| **Icons** | Lucide React 0.400 |
| **Linting** | Biome |
| **TypeScript** | 5.6 |

## Development

```powershell
cd webapp
npm install
npm run dev          # :11967, proxies /api → :11966
```

The Vite proxy forwards `/api/*` to `http://127.0.0.1:11966`.

## Production Build

```powershell
npm run build        # outputs to dist/
npm run preview      # serve dist/ locally
```

