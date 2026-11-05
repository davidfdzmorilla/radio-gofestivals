import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '··';
  // Por caracteres (code points), no por unidades UTF-16: slice(0, 2) y word[0]
  // parten por la mitad emojis y letras decorativas (𝗥𝗔𝗗𝗜𝗢, 🎵) y dejan un
  // surrogate suelto que el servidor serializa como U+FFFD y el cliente no
  // -> error de hidratación (React #418) y un "�" visible.
  const chars = (word: string): string[] => Array.from(word);
  if (words.length === 1) return chars(words[0]!).slice(0, 2).join('').toUpperCase();
  return (chars(words[0]!)[0]! + chars(words[1]!)[0]!).toUpperCase();
}
