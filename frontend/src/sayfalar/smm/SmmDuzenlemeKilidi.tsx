import { DUZENLEME_KILITLI_METNI, DuzenlemeKilidi, useDuzenlemeKilidi } from "@/bilesenler/DuzenlemeKilidi";
import { useOturum } from "@/bilesenler/GirisKapisi";

/** Kapatılmış dönemde düzenleme açık olsa da yazılamaz; şeritte ve düğme ipuçlarında bu metin görünür. */
export const DONEM_KAPALI_METNI = "Dönem kapatıldı; değişiklik için önce kilidi açın.";
const DONEM_KAPALI_NEDENI = "Dönem kapatıldı";

/**
 * Maliyet Muhasebesi'nde yazabilen roller: Genel Direktör ve Muhasebe (sunucudaki kimlik_servisi.yazabilir_mi ile aynı).
 * Satın alma ve izleyici SMM'ye yazamaz. Giriş zorunlu değilse (tek kullanıcılı kurulum) herkes yazar.
 */
export function useSmmYazabilir(): boolean {
  const { girisZorunlu, rol } = useOturum();
  return !girisZorunlu || rol === "genel_direktor" || rol === "muhasebe";
}

export interface SmmYazmaKilidi {
  /** Yazma alanları kapalı mı (düzenleme kilitli, rol yazamıyor ya da dönem kapatılmış). */
  kilitli: boolean;
  donemKilitli: boolean;
  duzenlemeKilitli: boolean;
  /** Düğme ipucu: "Dönem kapatıldı" / "Düzenleme kilitli". */
  neden: string | undefined;
}

/**
 * SMM sayfalarının tek "yazılamaz" bayrağı. Fiyat Çalışması'yla AYNI düzenleme kilidini kullanır (sekme genelinde tek kilit);
 * senaryo kilidi yerine dönem kilidine bakar. Dönem kapatma / kilit açma bu bayraktan bağımsızdır.
 */
export function useSmmYazmaKilidi(donemKilitli = false): SmmYazmaKilidi {
  const { acik } = useDuzenlemeKilidi();
  const yazabilir = useSmmYazabilir();
  const duzenlemeKilitli = !(acik && yazabilir);
  return {
    kilitli: donemKilitli || duzenlemeKilitli,
    donemKilitli,
    duzenlemeKilitli,
    neden: donemKilitli ? DONEM_KAPALI_NEDENI : duzenlemeKilitli ? DUZENLEME_KILITLI_METNI : undefined,
  };
}

/** SMM sayfalarının düzenleme kilidi şeridi (başlığın altında; Fiyat Çalışması'ndakiyle aynı bileşen ve aynı kilit). */
export function SmmDuzenlemeKilidi({ donemKilitli = false }: { donemKilitli?: boolean }) {
  const yazabilir = useSmmYazabilir();
  const { rol } = useOturum();
  return (
    <DuzenlemeKilidi
      senaryosuz
      yazabilir={yazabilir}
      yazamazMetni={
        rol === "satin_alma"
          ? "Düzenleme kilitli. Satın alma rolüyle Maliyet Muhasebesi'nde değişiklik yapılamaz."
          : "Düzenleme kilitli. Bu rolle Maliyet Muhasebesi'nde değişiklik yapılamaz."
      }
      engelMetni={donemKilitli ? DONEM_KAPALI_METNI : null}
    />
  );
}
