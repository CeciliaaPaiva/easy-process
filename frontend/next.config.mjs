/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { isServer }) => {
    if (!isServer) {
      // bpmn-js uses some Node.js built-ins that need to be shimmed in browser
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
        path: false,
        process: false,
      }
    }
    return config
  },
}

export default nextConfig
