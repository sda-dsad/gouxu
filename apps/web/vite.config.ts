import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({ plugins: [vue()], server: { proxy: { '/api': {target:'http://127.0.0.1:8000',changeOrigin:false} } }, build: { sourcemap: false, rollupOptions: { output: { manualChunks: (id:string) => id.includes('node_modules/three') ? 'three' : id.includes('node_modules/vue') || id.includes('node_modules/@vue') || id.includes('node_modules/pinia') ? 'vue' : undefined } } } })
