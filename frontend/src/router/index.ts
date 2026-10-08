import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import { useSessionStore } from '@/stores/session.ts'
import { useConfigStore } from '@/stores/backendConfig.ts'
import { checkPlayerExists } from '@/api/playersAPI.ts'
import { fetchConfig } from '@/api/backendConfigAPI.ts'

/**
 * Vue Router configuration defining all application routes.
 * - `/` – Login page
 * - `/home` – Main game home (requires auth)
 * - `/about` – About page
 * - `/config` – Backend LLM/transcription config (lazy-loaded)
 * - `/rulebook` – Rulebook viewer (lazy-loaded)
 * - `/timeline` – Session timeline (lazy-loaded, requires auth)
 */
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    /** Login route – the landing page for unauthenticated users. */
    {
      path: '/',
      name: 'login',
      component: LoginView,
    },
    /** Home route – the main game dashboard, requires an active session. */
    {
      path: '/home',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true },
    },
    /** About page. */
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/AboutView.vue'),
    },
    /** Config page – LLM selection, transcription model, embedding settings. */
    {
      path: '/config',
      name: 'config',
      component: () => import('../views/ConfigView.vue'),
    },
    /** Rulebook page – browse SRD documents. */
    {
      path: '/rulebook',
      name: 'rulebook',
      component: () => import('../views/RulebookView.vue'),
    },
    /** Timeline page – view and manage session timeline events. */
    {
      path: '/timeline',
      name: 'timeline',
      component: () => import('../views/TimelineView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

/**
 * Global navigation guard.
 * - Checks authentication for protected routes.
 * - Validates the player still exists on the backend.
 * - Redirects logged-in users away from login.
 * - Pre-fetches backend config when navigating to /config.
 */
router.beforeEach(async (to) => {
  const store = useSessionStore()

  if (to.meta.requiresAuth) {
    if (!store.currentPlayer) return { name: 'login' }

    try {
      const res = await checkPlayerExists(store.currentPlayer.id)
      if (!res.exists) {
        store.clearSession()
        return { name: 'login' }
      }
    } catch (err) {
      console.error('Fehler beim Prüfen des Players:', err)
    }
  }

  if (to.meta.requiresAuth && !store.currentPlayer) {
    return { name: 'login' }
  }

  if (to.name === 'login' && store.currentPlayer) {
    return { name: 'home' }
  }

  if (to.name === 'config') {
    try {
      const config = await fetchConfig()
      const configStore = useConfigStore()
      configStore.setConfig(config)
    } catch (error) {
      console.error('Error loading config:', error)
    }
  }
})

export default router
