import { defineStore } from 'pinia'

export type RoleCode = 'doctor' | 'patient' | 'knowledge_admin'

export const useAppStore = defineStore('app', {
  state: () => ({
    currentRole: 'doctor' as RoleCode
  }),
  actions: {
    setRole(role: RoleCode) {
      this.currentRole = role
    }
  }
})

