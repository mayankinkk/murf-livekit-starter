'use client';

/**
 * Persistent, automatic caller identity (Day 4).
 *
 * A UUID is generated once per browser and stored in localStorage so the same
 * browser is recognised on every future call. The ID travels to the agent via
 * the LiveKit participant attributes and is used as the MongoDB key for the
 * caller's memory. The user never has to see or enter it.
 */

const STORAGE_KEY = 'rupeegpt_user_id';

function generateUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID.
  return `rupeegpt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function getOrCreateUserId(): string {
  if (typeof window === 'undefined') {
    // Server-side render pass — a real ID will be created on the client.
    return '';
  }
  try {
    const existing = window.localStorage.getItem(STORAGE_KEY);
    if (existing) {
      return existing;
    }
    const id = generateUuid();
    window.localStorage.setItem(STORAGE_KEY, id);
    return id;
  } catch {
    // localStorage unavailable (private/restricted contexts): still return a
    // stable value for the current page so the agent always has an ID to use.
    return generateUuid();
  }
}
