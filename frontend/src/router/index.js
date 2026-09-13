import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginView from '../views/LoginView.vue'
import RunListView from '../views/RunListView.vue'
import RunCreateView from '../views/RunCreateView.vue'
import RunDetailView from '../views/RunDetailView.vue'
import EventTimelineView from '../views/EventTimelineView.vue'
import LineageView from '../views/LineageView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/', redirect: '/runs' },
    { path: '/runs', name: 'runs', component: RunListView },
    { path: '/runs/new', name: 'run-create', component: RunCreateView, meta: { researcher: true } },
    { path: '/runs/:id', name: 'run-detail', component: RunDetailView },
    { path: '/runs/:id/events', name: 'run-events', component: EventTimelineView },
    { path: '/runs/:id/lineage', name: 'run-lineage', component: LineageView },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.researcher && auth.role !== 'researcher') {
    return { name: 'runs' }
  }
  if (to.name === 'login' && auth.token) {
    return { name: 'runs' }
  }
  return true
})

export default router
