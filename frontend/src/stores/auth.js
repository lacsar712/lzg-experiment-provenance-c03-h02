import { defineStore } from 'pinia'
import { ref } from 'vue'

const TOKEN_KEY = 'ep_token'
const USER_KEY = 'ep_user'

export const useAuthStore = defineStore('auth', () => {
  const saved = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const username = ref(saved?.username || '')
  const role = ref(saved?.role || '')

  function setSession(payload) {
    token.value = payload.access_token
    username.value = payload.username
    role.value = payload.role
    localStorage.setItem(TOKEN_KEY, payload.access_token)
    localStorage.setItem(
      USER_KEY,
      JSON.stringify({ username: payload.username, role: payload.role }),
    )
  }

  function logout() {
    token.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  return { token, username, role, setSession, logout }
})
