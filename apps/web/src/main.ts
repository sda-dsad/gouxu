import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './theme/style.css'
createApp(App).use(createPinia()).mount('#app')
