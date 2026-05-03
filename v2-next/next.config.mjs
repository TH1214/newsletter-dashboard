/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  basePath: '/newsletter-dashboard',
  assetPrefix: '/newsletter-dashboard',
};
export default nextConfig;
