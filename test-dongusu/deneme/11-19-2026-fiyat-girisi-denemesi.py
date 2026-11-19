"""Birim fiyat girişlerinin her ekrana ve hesaba doğru yansıdığını dener (test sunucusu 8048, uydurma veri).

Kullanım (proje kökünden; 8048'de test veritabanıyla sunucu açıkken):
    .venv/Scripts/python test-dongusu/deneme/11-19-2026-fiyat-girisi-denemesi.py

Bütçenin (#1, kilitli) temiz bir kopyası açılır, her fiyat girişi orada yapılır. Beklenen etki formülle bağımsız hesaplanır:
  maliyete giren birim fiyat = girilen x (1 + enflasyon) [Satın alma, TL] | girilen [Ziraat, TL] | girilen x kur [döviz]
  satır tutarı farkı = birim fiyat farkı x brüt miktar;  ürün maliyeti farkı = satır farkı x (1 + finansman oranı)
"""
from decimal import Decimal as D

import httpx

A = "http://127.0.0.1:8048"
SONUC: list[str] = []
c = httpx.Client(base_url=A, timeout=180)


def kontrol(ad, gercek, beklenen, tol="0.0005"):
    g, b = D(str(gercek)), D(str(beklenen))
    ok = abs(g - b) <= D(tol)
    SONUC.append(f"{'TUTTU ' if ok else 'TUTMADI'} · {ad}: ekran {g.quantize(D('0.0001'))} · beklenen {b.quantize(D('0.0001'))}")
    return ok


def esit(ad, kosul, not_=""):
    SONUC.append(f"{'TUTTU ' if kosul else 'TUTMADI'} · {ad}{' · ' + not_ if not_ else ''}")


def al(yol):
    r = c.get(yol)
    r.raise_for_status()
    return r.json()


def hesap(kod, sen, tarih=None):
    g = {"senaryo_id": sen}
    if tarih:
        g["tarih"] = tarih
    r = c.post(f"/api/v1/urunler/{kod}/hesapla", json=g)
    r.raise_for_status()
    return r.json()


def satir(h, kod):
    return next((s for s in h["satirlar"] if s["kod"] == kod), None)


def ekranlar(sen):
    """Bütün ekranların okuduğu değerler (ürün kodu -> değer)."""
    gb = {k["kod"]: D(k["maliyet_tl"]) for k in al(f"/api/v1/urunler?senaryo={sen}&boyut=100&yenile=true")["kayitlar"] if k.get("maliyet_tl")}
    kar = {k["kod"]: D(k["maliyet"]) for k in al(f"/api/v1/analiz/karlilik?senaryo={sen}")["kayitlar"] if k.get("maliyet")}
    hf = {k["kod"]: D(k["maliyet"]) for k in al(f"/api/v1/analiz/hedef-fiyat?senaryo={sen}&marj=0.2")["kayitlar"] if k.get("maliyet")}
    kr = {k["kod"]: D(k["maliyet"]) for k in al(f"/api/v1/analiz/kur-riski?senaryo={sen}&oran=0.10")["kayitlar"] if k.get("maliyet")}
    li = {k["kod"]: k for k in al(f"/api/v1/liste-calismasi?senaryo={sen}&pazar=yurtici").get("kayitlar", [])}
    yo = al(f"/api/v1/yonetim/ozet?senaryo={sen}&yenile=true")
    return {"genel": gb, "karlilik": kar, "hedef": hf, "kur": kr, "liste": li, "yonetim_yillik": D(yo["kur_riski"]["yillik_maliyet_tl"])}


def ekran_tutarliligi(ad, sen, kodlar, h_maliyet):
    e = ekranlar(sen)
    for kod in kodlar:
        m = h_maliyet[kod]
        for ekran in ("genel", "karlilik", "hedef", "kur"):
            if kod in e[ekran]:
                kontrol(f"{ad} · {kod} · {ekran} = ürün ekranı", e[ekran][kod], m, "0.0001")
        if kod in e["liste"] and e["liste"][kod].get("satis"):
            kontrol(f"{ad} · {kod} · liste satış = maliyet x 1,20", e["liste"][kod]["satis"], m * D("1.2"), "0.0001")
    return e


def fiyat_gir(kod, sen, fiyat, tarih="2026-11-19", neden="fiyat girişi denemesi"):
    r = c.post(f"/api/v1/malzemeler/{kod}/fiyatlar?senaryo={sen}", json={"fiyat": str(fiyat), "gecerlilik_basi": tarih, "neden": neden, "onay": True})
    esit(f"fiyat kaydı {kod} = {fiyat}", r.status_code == 201, f"HTTP {r.status_code} {r.text[:120] if r.status_code != 201 else ''}")


def main():
    r = c.post("/api/v1/kimlik/giris", json={"kullanici_adi": "muhasebe1", "sifre": "Deneme2026!"})
    r.raise_for_status()
    kop = c.post("/api/v1/senaryolar/1/kopyala", json={"sezon_ad": "2026-2027", "ad": "Fiyat girişi denemesi", "tur": "fiyat_calismasi",
                                                      "neden": "Birim fiyat girişlerinin yansıma denemesi",
                                                      "kopyala": {"receteler": True, "fiyatlar": True, "parametreler": True, "gider": True,
                                                                  "uretim": True, "fire_kurallari": True, "sablon": False}})
    kop.raise_for_status()
    j = kop.json()
    S = j["senaryo"]["id"] if "senaryo" in j else j["id"]
    print("deneme çalışması #", S)
    p = al(f"/api/v1/parametreler?senaryo={S}")
    enf, kur_usd, kur_eur = D(p["enflasyon"]), D(p["kur.USD"]), D(p["kur.EUR"])
    fin = D(p["faiz.TL"]) * D(p["stok_ay.TL"]) / 12
    URUNLER = sorted(ekranlar(S)["genel"].keys())
    once = {k: hesap(k, S) for k in URUNLER}
    bütce_once = dict(ekranlar(1)["genel"])

    def adim(ad, malzeme, yeni_fiyat_giris, etkili_carpani, uygula, kapsam=None):
        kullananlar = [k for k in URUNLER if satir(once[k], malzeme)] if kapsam is None else kapsam
        if not kullananlar:
            esit(f"{ad}: {malzeme} hiçbir reçetede yok", False)
            return
        uygula()
        sonra = {k: hesap(k, S) for k in URUNLER}
        for k in URUNLER:
            m0, m1 = D(once[k]["toplamlar"]["maliyet_tl"]), D(sonra[k]["toplamlar"]["maliyet_tl"])
            if k in kullananlar:
                s0, s1 = satir(once[k], malzeme), satir(sonra[k], malzeme)
                kontrol(f"{ad} · {k} · reçetedeki birim fiyat = girilen", s1["birim_fiyat"], D(yeni_fiyat_giris))
                beklenen_satir = (D(yeni_fiyat_giris) - D(s0["birim_fiyat"])) * D(s1["brut_miktar"]) * etkili_carpani
                kontrol(f"{ad} · {k} · satır tutarı farkı", D(s1["tutar"]) - D(s0["tutar"]), beklenen_satir)
                kontrol(f"{ad} · {k} · birim maliyet farkı (x finansman {1 + fin})", m1 - m0, beklenen_satir * (1 + fin))
            else:
                kontrol(f"{ad} · {k} · etkilenmemeli", m1, m0, "0.00001")
        ekran_tutarliligi(ad, S, URUNLER, {k: D(v["toplamlar"]["maliyet_tl"]) for k, v in sonra.items()})
        once.update(sonra)

    # 1. Malzeme Fiyatları › Fiyat değiştir (Satın alma, TL): kapak 2,15 -> 2,50
    adim("1 Satın alma TL (kapak)", "99.20.003", "2.50", 1 + enf, lambda: fiyat_gir("99.20.003", S, "2.50"))
    # 2. Ziraat, TL: taze hıyar 18,50 -> 20,00 (enflasyon payı olmamalı)
    adim("2 Ziraat TL (hıyar)", "99.10.001", "20.00", D(1), lambda: fiyat_gir("99.10.001", S, "20.00"))
    # 3. Dövizli malzeme: reçetelerde USD ile gelen ilk malzeme
    usd = next((s["kod"] for k in URUNLER for s in once[k]["satirlar"] if s.get("doviz") == "USD" and D(s.get("birim_fiyat") or 0) > 0), None)
    eur = next((s["kod"] for k in URUNLER for s in once[k]["satirlar"] if s.get("doviz") == "EUR" and D(s.get("birim_fiyat") or 0) > 0), None)
    for kod, kur, ad in ((usd, kur_usd, "USD"), (eur, kur_eur, "EUR")):
        if not kod:
            esit(f"3 {ad} malzeme bulunamadı", False)
            continue
        mevcut = next(s for k in URUNLER for s in once[k]["satirlar"] if s["kod"] == kod)
        ham = D(mevcut["birim_fiyat"])
        yeni = (ham * D("1.10")).quantize(D("0.0001"))
        adim(f"3 Döviz {ad} ({kod} {ham} -> {yeni})", kod, yeni, kur, lambda kod=kod, yeni=yeni: fiyat_gir(kod, S, yeni))
    # 4. İleri tarihli fiyat: bugünkü hesap değişmemeli, o tarihten sonraki hesap değişmeli
    k_once = D(hesap("03.99.001", S)["toplamlar"]["maliyet_tl"])
    fiyat_gir("99.20.005", S, "0.80", tarih="2027-03-01", neden="ileri tarihli fiyat denemesi")
    kontrol("4 İleri tarihli fiyat · bugünkü hesap değişmedi (03.99.001)", hesap("03.99.001", S)["toplamlar"]["maliyet_tl"], k_once, "0.00001")
    ileri = hesap("03.99.001", S, "2027-03-02")
    s = satir(ileri, "99.20.005")
    kontrol("4 İleri tarihli fiyat · 02.03.2027 hesabında birim fiyat", s["birim_fiyat"], D("0.80"))
    kontrol("4 İleri tarihli fiyat · 02.03.2027 satır tutarı = 0,80 x 1,25 x brüt", s["tutar"], D("0.80") * (1 + enf) * D(s["brut_miktar"]))
    # 5. Yeni malzeme kartı + ilk fiyat, sonra ürün ekranında reçeteye satır olarak eklenir (03.99.006)
    r = c.post("/api/v1/malzemeler", json={"kod": "99.20.099", "ad": "Deneme Etiket Teneke", "tip": "0008-Ambalaj Malzeme", "birim": "AD", "para_birimi": "TL", "zs": "S"})
    esit("5 Yeni malzeme kartı açıldı", r.status_code in (200, 201), f"HTTP {r.status_code}")
    fiyat_gir("99.20.099", S, "1.00", tarih="2026-06-01")
    m0 = D(hesap("03.99.006", S)["toplamlar"]["maliyet_tl"])
    rec = al(f"/api/v1/urunler/03.99.006/recete?senaryo={S}")["satirlar"]
    kay = c.post("/api/v1/urunler/03.99.006/kaydet", json={"senaryo_id": S, "neden": "Yeni malzeme reçeteye eklendi", "hesabi_kaydet": False,
                                                           "override": {"eklenen_satirlar": [{"malzeme_kodu": "99.20.099", "ad": "Deneme Etiket Teneke", "miktar": "1", "birim": "AD"}]}})
    if kay.status_code != 200:   # override yalnız hesapla birlikte; kalıcı ekleme için tam reçete gönder
        satirlar = [{k: v for k, v in x.items() if k in ("malzeme_kodu", "ad", "miktar", "birim", "fire_override", "dugum_tipi", "brut_miktar_elle",
                                                       "birim_fiyat_elle", "seviye", "zs_elle", "para_birimi_elle")} for x in rec]
        satirlar.append({"malzeme_kodu": "99.20.099", "ad": "Deneme Etiket Teneke", "miktar": "1", "birim": "AD"})
        kay = c.post("/api/v1/urunler/03.99.006/kaydet", json={"senaryo_id": S, "neden": "Yeni malzeme reçeteye eklendi", "recete": satirlar, "hesabi_kaydet": False})
    esit("5 Reçeteye yeni satır kaydedildi", kay.status_code == 200, f"HTTP {kay.status_code} {kay.text[:150] if kay.status_code != 200 else ''}")
    h6 = hesap("03.99.006", S)
    s = satir(h6, "99.20.099")
    if s:
        kontrol("5 Yeni malzeme · birim fiyat = girilen", s["birim_fiyat"], D("1.00"))
        kontrol("5 Yeni malzeme · satır tutarı = 1,00 x 1,25 x brüt", s["tutar"], D("1.00") * (1 + enf) * D(s["brut_miktar"]))
        kontrol("5 Yeni malzeme · 03.99.006 maliyet farkı", D(h6["toplamlar"]["maliyet_tl"]) - m0, D(s["tutar"]) * (1 + fin))
    else:
        esit("5 Yeni malzeme reçetede görünüyor", False)
    # 6. Ürün ekranında satıra elle birim fiyat (yalnız o ürün değişmeli): 03.99.002'de kavanoz 720 satırı 12,00 TL
    once.update({k: hesap(k, S) for k in URUNLER})
    rec2 = al(f"/api/v1/urunler/03.99.002/recete?senaryo={S}")["satirlar"]
    yeni_rec = []
    for x in rec2:
        y = {k: v for k, v in x.items() if k in ("malzeme_kodu", "ad", "miktar", "birim", "fire_override", "dugum_tipi", "brut_miktar_elle", "birim_fiyat_elle",
                                                 "seviye", "zs_elle", "para_birimi_elle")}
        if x["malzeme_kodu"] == "99.20.002":
            y["birim_fiyat_elle"] = "12.00"
        yeni_rec.append(y)

    def elle():
        k = c.post("/api/v1/urunler/03.99.002/kaydet", json={"senaryo_id": S, "neden": "Kavanoz 720 elle fiyat", "recete": yeni_rec, "hesabi_kaydet": True})
        esit("6 Elle birim fiyat kaydedildi", k.status_code == 200, f"HTTP {k.status_code} {k.text[:150] if k.status_code != 200 else ''}")
    adim("6 Elle birim fiyat (03.99.002 kavanoz 720)", "99.20.002", "12.00", 1 + enf, elle, kapsam=["03.99.002"])
    # 7. Önemli malzemeler, zam etkisi, fiyat eğilimi, teklif, günlük
    om = {x["kod"]: x for x in al(f"/api/v1/analiz/onemli-malzemeler?senaryo={S}")["satirlar"]}
    if "99.20.003" in om:
        x = om["99.20.003"]
        kontrol("7 Önemli malzemeler · kapak yıllık tutar / miktar = maliyete giren fiyat", D(x["yillik_tutar_tl"]) / D(x["yillik_miktar"]), D("2.50") * (1 + enf), "0.001")
    fe = {x["kod"]: x for x in al(f"/api/v1/analiz/fiyat-egilimi?senaryo={S}")["satirlar"]}
    kontrol("7 Fiyat eğilimi · kapak son fiyat", fe["99.20.003"]["son_fiyat"], "2.50")
    kontrol("7 Fiyat eğilimi · hıyar son fiyat", fe["99.10.001"]["son_fiyat"], "20.00")
    z = al(f"/api/v1/analiz/zam-etkisi?senaryo={S}&malzeme=99.20.003&oran=0.10")
    for x in z["kayitlar"]:
        kontrol(f"7 Zam etkisi · {x['kod']} bugünkü maliyet = ürün ekranı", x["maliyet_once"], once[x["kod"]]["toplamlar"]["maliyet_tl"] if x["kod"] in once else hesap(x["kod"], S)["toplamlar"]["maliyet_tl"], "0.0001")
    hz = c.post("/api/v1/urunler/03.99.001/hesaplar", json={"senaryo_id": S}).json()
    tk = c.post(f"/api/v1/hesaplar/{hz['id']}/teklifler", json={"kar_orani": "0.17", "musteri": "Deneme", "notu": "fiyat denemesi"}).json()
    kontrol("7 Teklif fiyatı = güncel maliyet x 1,17", tk["fiyat_tl"], D(hesap("03.99.001", S)["toplamlar"]["maliyet_tl"]) * D("1.17"), "0.0001")
    g = al(f"/api/v1/gunluk?senaryo={S}&tur=fiyat&boyut=50")["kayitlar"]
    esit("7 Günlükte kapak fiyatı okunur", any("99.20.003" in x["baslik"] and (x.get("yeni") or "").startswith("2,50") for x in g),
         next((f"{x['baslik']}: {x.get('eski')} → {x.get('yeni')}" for x in g if "99.20.003" in x["baslik"]), "kayıt yok"))
    # 8. Başka çalışma etkilenmedi (bütçe #1)
    b = ekranlar(1)["genel"]
    esit("8 Bütçe çalışması (#1) hiç değişmedi", all(abs(b[k] - bütce_once[k]) < D("0.00001") for k in b))

    tuttu = sum(1 for x in SONUC if x.startswith("TUTTU"))
    print("\n".join(x for x in SONUC if not x.startswith("TUTTU")) or "(tutmayan yok)")
    print(f"\nTOPLAM: {tuttu} / {len(SONUC)} tuttu · deneme çalışması #{S}")
    with open(__file__.replace(".py", "-sonuc.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(SONUC) + f"\n\nTOPLAM: {tuttu} / {len(SONUC)}\n")


if __name__ == "__main__":
    main()
