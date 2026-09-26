/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendTarget =
      process.env.BACKEND_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://127.0.0.1:8000/api/v1";
    const dest = backendTarget.endsWith("/api/v1")
      ? `${backendTarget}/:path*`
      : `${backendTarget}/api/v1/:path*`;
    return [
      {
        source: "/api/v1/:path*",
        destination: dest,
      },
    ];
  },
};

export default nextConfig;
