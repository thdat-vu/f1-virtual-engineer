import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "F1 Virtual Engineer",
    short_name: "F1 VE",
    description:
      "Virtual F1 race engineer for telemetry, strategy signals, and explainable mission-control workflows.",
    start_url: "/",
    display: "standalone",
    background_color: "#05070b",
    theme_color: "#05070b",
    icons: [
      {
        src: "/icon.png",
        sizes: "1254x1254",
        type: "image/png",
      },
      {
        src: "/apple-icon.png",
        sizes: "1254x1254",
        type: "image/png",
      },
    ],
  };
}
