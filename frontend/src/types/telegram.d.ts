// Telegram WebApp types
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initDataUnsafe?: {
          user?: {
            id: number
            first_name?: string
            last_name?: string
            username?: string
            language_code?: string
            is_premium?: boolean
            photo_url?: string
          }
          query_id?: string
          auth_date?: number
        }
        initData?: string
        version?: string
        platform?: string
        colorScheme?: 'light' | 'dark'
        themeParams?: any
        isExpanded?: boolean
        viewportHeight?: number
        viewportStableHeight?: number
        headerColor?: string
        backgroundColor?: string
        isClosingConfirmationEnabled?: boolean
        BackButton?: any
        MainButton?: any
        HapticFeedback?: any
        CloudStorage?: any
        BiometricManager?: any
        ready?: () => void
        expand?: () => void
        close?: () => void
        enableClosingConfirmation?: () => void
        disableClosingConfirmation?: () => void
        onEvent?: (eventType: string, eventHandler: () => void) => void
        offEvent?: (eventType: string, eventHandler: () => void) => void
        sendData?: (data: string) => void
        openLink?: (url: string, options?: any) => void
        openTelegramLink?: (url: string) => void
        openInvoice?: (url: string, callback?: (status: string) => void) => void
        showPopup?: (params: any, callback?: (id: string) => void) => void
        showAlert?: (message: string, callback?: () => void) => void
        showConfirm?: (message: string, callback?: (confirmed: boolean) => void) => void
        showScanQrPopup?: (params: any, callback?: (data: string) => void) => void
        closeScanQrPopup?: () => void
        readTextFromClipboard?: (callback?: (text: string) => void) => void
        requestWriteAccess?: (callback?: (granted: boolean) => void) => void
        requestContact?: (callback?: (granted: boolean) => void) => void
      }
    }
  }
}

export {}
