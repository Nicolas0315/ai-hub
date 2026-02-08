import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/Katala",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
