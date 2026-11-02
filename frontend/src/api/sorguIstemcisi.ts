import { QueryClient } from "@tanstack/react-query";
import { ApiHatasi } from "./istemci";

/** 4xx yanıtları yeniden denenmez (aynı istek aynı hatayı verir); ağ/5xx en fazla iki kez denenir. */
export const yenidenDene = (n: number, e: unknown): boolean =>
  !(e instanceof ApiHatasi && e.durum >= 400 && e.durum < 500) && n < 2;

export function sorguIstemcisi(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: yenidenDene }, mutations: { retry: 0 } } });
}
