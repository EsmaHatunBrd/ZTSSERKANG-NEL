import type { ListePazari } from "@/api/tipler";
import { D } from "@/yardimcilar/para";

export const PAZAR_ADI: Record<ListePazari, string> = { yurtici: "Yurtiçi", yurtdisi: "Yurtdışı" };
export const PAZARLAR: ListePazari[] = ["yurtici", "yurtdisi"];

/** API sayı metni -> kutu metni ("0.63" -> "0,63"). */
export const kutuMetni = (x: string) => D(x).toFixed().replace(".", ",");

/** Yuvarlama adımı metni: "0.05" -> "0,05", "0.10" -> "0,10", "1" -> "1". */
export const adimMetni = (x: string) => (D(x).isInteger() ? D(x).toFixed(0) : D(x).toFixed(2).replace(".", ","));

/** "En yakın 0,05 TL". */
export const yuvarlamaEtiketi = (x: string) => `En yakın ${adimMetni(x)} TL`;
