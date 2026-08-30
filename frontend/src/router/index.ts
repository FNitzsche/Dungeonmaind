import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView/HomeView.vue'
import LoginView from '@/views/LoginView.vue'
import { useSessionStore } from '@/stores/session.ts'
import { useConfigStore } from "@/stores/backendConfig.ts"
import { checkPlayerExists } from "@/api/playersAPI.ts";
import { fetchConfig } from "@/api/backendConfigAPI.ts";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/home',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true },
    },
    {
      path: '/timeline',
      name: 'timeline',
      component: () =>
        import('../views/TimelineView/TimelineView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/about',
      name: 'about',
      component: () => import('../views/AboutView.vue'),
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('../views/ConfigView.vue'),
    },
    {
      path: '/rulebook',
      name: 'rulebook',
      component: () => import('../views/RulebookView.vue'),
    },
  ],
});

router.beforeEach(async (to) => {
  const store = useSessionStore();

  if (to.meta.requiresAuth) {
    if (!store.currentPlayer) return { name: "login" };

    try {
      const res = await checkPlayerExists(store.currentPlayer.id);
      if (!res.exists) {
        store.clearSession();
        return { name: "login" };
      }
    } catch (err) {
      console.error("Fehler beim Prüfen des Players:", err);
      store.clearSession();
      return { name: "login" };
    }
  }

  if (to.meta.requiresAuth && !store.currentPlayer) {
    return { name: "login" };
  }

  if (to.name === "login" && store.currentPlayer) {
    return { name: "home" };
  }

  if (to.name === "config") {
    try {
      const config = await fetchConfig();
      const configStore = useConfigStore();
      configStore.setConfig(config);
    } catch (error) {
      console.error("Error loading config:", error);
    }
  }
});

export default router
