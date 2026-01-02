import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Platform detection utility
export function isMac(): boolean {
  return typeof navigator !== 'undefined' && navigator.platform.toUpperCase().indexOf('MAC') >= 0;
}

// Keyboard shortcut formatting utility
export function formatKeyboardShortcut(key: string): string {
  const modifierKey = isMac() ? '⌘' : 'Ctrl';
  return `${modifierKey}${key.toUpperCase()}`;
}

/**
 * Format quantity for display, handling both whole and fractional shares.
 * Shows up to 4 decimal places for fractional quantities, no decimals for whole.
 */
export function formatQuantity(qty: number | null | undefined): string {
  if (qty === null || qty === undefined) return 'N/A';
  
  const absQty = Math.abs(qty);
  
  // Check if it's a whole number
  if (absQty === Math.floor(absQty)) {
    return absQty.toLocaleString();
  }
  
  // Fractional - show up to 4 decimal places, trim trailing zeros
  return absQty.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 4,
  });
}

/**
 * Format quantity with "shares" suffix
 */
export function formatShares(qty: number | null | undefined): string {
  const formatted = formatQuantity(qty);
  if (formatted === 'N/A') return formatted;
  return `${formatted} shares`;
}

// Provider color utility for consistent styling across components
export function getProviderColor(provider: string): string {
  return 'bg-gray-600/20 text-primary border-gray-600/40';
  // switch (provider.toLowerCase()) {
  //   case 'anthropic':
  //     return 'bg-orange-600/20 text-orange-300 border-orange-600/40';
  //   case 'google':
  //     return 'bg-green-600/20 text-green-300 border-green-600/40';
  //   case 'groq':
  //     return 'bg-red-600/20 text-red-300 border-red-600/40';
  //   case 'deepseek':
  //     return 'bg-blue-600/20 text-blue-300 border-blue-600/40';
  //   case 'openai':
  //     return 'bg-gray-900/60 text-gray-200 border-gray-700/60';
  //   case 'ollama':
  //     return 'bg-white/90 text-gray-800 border-gray-300';
  //   default:
  //     return 'bg-gray-600/20 text-gray-300 border-gray-600/40';
  // }
}
