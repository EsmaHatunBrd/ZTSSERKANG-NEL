"""'Kimden ne istenecek' listesini üretir: sablonlar/11-16-2026-istenecek-dosyalar-listesi.xlsx (yeniden çalıştırılabilir)."""
import pathlib
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

KLASOR = pathlib.Path(__file__).resolve().parent
CIKTI = KLASOR / "11-16-2026-istenecek-dosyalar-listesi.xlsx"

SABLON = "Şablon doldurulur"
CANIAS = "Canias raporu olduğu gibi"
KENDI = "Kendi Excel'i olduğu gibi"

# (kimden, no, ne, nasıl, dosya, ne zaman, zorunlu, not)
SATIRLAR = [
    ("Satın alma", "01", "Satın alma fiyat listesi (malzeme kartı + bütçe fiyatı)", SABLON, "11-16-2026-01-satin-alma-fiyat-listesi.xlsx",
     "Sezon başı; yeni malzeme açılınca", "Evet", "Fiyatlar sayı hücresi; dövizli fiyatın para birimi ayrı sütunda."),
    ("Satın alma", "02", "Malzeme fiyat listesi (zam / revize)", SABLON, "11-16-2026-02-malzeme-fiyat-listesi.xlsx",
     "Fiyat değiştikçe", "Gerektikçe", "Yalnız değişen fiyatlar yeterli; geçerlilik tarihi yazılsın."),
    ("Üretim planlama", "03", "Üretim adetleri (vardiya kapasitesi, hedef üretim)", SABLON, "11-16-2026-03-uretim-adetleri.xlsx",
     "Sezon başı; plan değişince", "Evet", "Ürün kodları ürün kartındakiyle aynı olmalı."),
    ("Muhasebe", "04", "Gider dağıtım (gider havuzları, paylar)", SABLON, "11-16-2026-04-gider-dagitim.xlsx",
     "Sezon başı (bütçe); revizede", "Evet", "Sabit hücre düzeni: satır/sütun eklenmez."),
    ("Ar-Ge / Üretim", "05", "Ürün reçetesi (yeni ürün ya da reçete değişikliği)", SABLON, "11-16-2026-05-urun-recetesi.xlsx",
     "Yeni ürün / reçete değişince", "Gerektikçe", "Fiyat Çalışması kitabı varsa ayrıca gerekmez."),
    ("Muhasebe", "06", "Stokta kalan (geçen yıldan devreden ürün stoku)", SABLON, "11-16-2026-06-stokta-kalan.xlsx",
     "Sezon başı", "Evet", "Enflasyon 0,40 ya da %40 yazılır (40 değil)."),
    ("Satış / Muhasebe", "07", "Satış geçmişi (geçen yıl satışları: ürün, müşteri, tarih, fiyat, adet)", SABLON, "11-16-2026-07-satis-gecmisi.xlsx",
     "Sezon başı; istenirse ay sonu", "Evet", "Canias satış raporundan doldurulur."),
    ("Satış / Pazarlama", "08", "Geçmiş yılların liste fiyatları (yalnız Berrak)", SABLON, "11-16-2026-08-liste-fiyatlari.xlsx",
     "Yılda bir, sezon başı", "Evet", "KDV hariç; pazar Yurtiçi / Yurtdışı."),
    ("Muhasebe", "—", "Fiyat Çalışması kitabı (bütçe)", KENDI, "Fiyat Çalışma - <sezon> - Berrak.xlsx",
     "Sezon başı", "Evet", "Varsa 01, 03, 04, 05 ayrıca istenmez; yalnız eksikler."),
    ("Canias sorumlusu / BT", "09", "Ürün ağacı dökümü (TBLRESULT)", CANIAS, "11-16-2026-09-canias-urun-agaci.xlsx (yalnız elle düzeltme için)",
     "Reçete değiştikçe", "Evet", "İlk seferde örnek rapor istenir."),
    ("Muhasebe (Canias'tan)", "10", "Alım ve satış hareketleri (HM-YM ALIŞ SATIŞ)", CANIAS, "11-16-2026-10-smm-alim-satis.xlsx (yedek)",
     "Her ay sonu", "Evet", "Tutar TL olmalı; ilk ay örnek rapor istenir."),
    ("Muhasebe (Canias'tan)", "11", "Alım iadeleri (İADELER)", CANIAS, "11-16-2026-11-smm-iadeler.xlsx (yedek)",
     "Her ay sonu (iade varsa)", "Varsa", "İade miktarı artı yazılır."),
    ("Üretim / Muhasebe (Canias'tan)", "12", "Üretim miktarları (ÜRETİM)", CANIAS, "11-16-2026-12-smm-uretim.xlsx (yedek)",
     "Her ay sonu", "Evet", "Ayın üretimi mi, yıl içi toplam mı? Muhasebeyle teyit edilecek."),
    ("Depo (sayım)", "13", "Dönem sonu sayım (DSS)", SABLON, "11-16-2026-13-smm-sayim.xlsx",
     "Her ay sonu", "Evet", "Sayım tutanağından; Canias sayım raporu varsa o da olur."),
    ("Kalite", "14", "Şahit numune (ŞAHİT)", SABLON, "11-16-2026-14-smm-sahit-numune.xlsx",
     "Her ay sonu (varsa)", "Varsa", "Toplam miktar J sütununda."),
    ("Muhasebe (Canias'tan)", "15", "Gider mizanı (720 / 730)", CANIAS, "11-16-2026-15-smm-gider-mizani.xlsx (yedek)",
     "Her ay sonu", "Evet", "3 haneli ana hesap satırları bulunmalı."),
    ("Muhasebe (Canias'tan)", "16", "Stok mizanı (150 / 151 / 152)", CANIAS, "11-16-2026-16-smm-stok-mizani.xlsx (yedek)",
     "Her ay sonu", "Evet", ""),
    ("Muhasebe", "—", "SMM dönem Excel'i (Excel'le kapatılan aylar için)", KENDI, "<AA-YYYY> SMM.xlsx",
     "Ay sonu (geçiş döneminde)", "Gerektikçe", "Aylık kaynaklar yüklenirse gerekmez."),
]

# Tek seferlik istekler: uygulamayı Canias raporlarına uyarlamak için örnekler
TEK_SEFER = [
    ("Canias sorumlusu / BT", "Canias rapor örnekleri (bir aylık): ürün ağacı, alım-satış, iadeler, üretim, gider mizanı, stok mizanı",
     "Uygulama bu raporları olduğu gibi okusun diye bir kez uyarlanacak", "En kısa sürede"),
    ("Canias sorumlusu / BT", "Her raporun Canias'taki adı / menü yolu ve filtreleri (dönem, depo, hesap aralığı)",
     "Her ay aynı raporun aynı ayarlarla alınması için", "Örneklerle birlikte"),
    ("Muhasebe", "Açık sorular formu (docs/aktarim) cevapları: üretim miktarı ayın mı yıl içi toplam mı, 720/730 dağıtım oranları",
     "Okuyucu ve hesap kuralları teyidi", "Görüşmede"),
]

YESIL = PatternFill("solid", fgColor="3F5A2A")
ACIK = PatternFill("solid", fgColor="EEF2E6")
INCE = Side(style="thin", color="BFC7B5")
KENAR = Border(left=INCE, right=INCE, top=INCE, bottom=INCE)


def baslik(ws, basliklar, genislikler):
    ws.append(basliklar)
    for i, (h, g) in enumerate(zip(basliklar, genislikler), start=1):
        c = ws.cell(row=1, column=i)
        c.font, c.fill, c.border = Font(bold=True, color="FFFFFF"), YESIL, KENAR
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[c.column_letter].width = g
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30


def govde(ws, satir_sayisi, sutun_sayisi):
    for r in range(2, satir_sayisi + 2):
        for k in range(1, sutun_sayisi + 1):
            c = ws.cell(row=r, column=k)
            c.alignment, c.border = Alignment(wrap_text=True, vertical="top"), KENAR
            if r % 2 == 0:
                c.fill = ACIK


wb = Workbook()
ws = wb.active
ws.title = "Kimden ne istenecek"
b = ["Kimden", "No", "Ne istenecek", "Nasıl", "Şablon / dosya", "Ne zaman", "Zorunlu mu", "Not", "İstendi", "Geldi", "Sorumlu (ad)"]
baslik(ws, b, [24, 6, 44, 24, 44, 26, 12, 46, 10, 10, 18])
for s in sorted(SATIRLAR, key=lambda x: (x[0], x[1])):
    ws.append(list(s) + ["", "", ""])
govde(ws, len(SATIRLAR), len(b))
dv = DataValidation(type="list", formula1='"Evet,Hayır"', allow_blank=True)
ws.add_data_validation(dv)
dv.add(f"I2:J{len(SATIRLAR) + 1}")
ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(b)).column_letter}{len(SATIRLAR) + 1}"

ws2 = wb.create_sheet("Tek seferlik istekler")
b2 = ["Kimden", "Ne istenecek", "Neden", "Ne zaman", "İstendi", "Geldi"]
baslik(ws2, b2, [24, 70, 50, 20, 10, 10])
for s in TEK_SEFER:
    ws2.append(list(s) + ["", ""])
govde(ws2, len(TEK_SEFER), len(b2))

ws3 = wb.create_sheet("Açıklama")
for satir in [
    ["Bu liste, uygulamaya yüklenecek dosyaların kimden ve ne zaman isteneceğini gösterir."],
    [""],
    ["Nasıl sütunu:"],
    [f"• {SABLON}: ilgili kişiye sablonlar/ klasöründeki dosya gönderilir, doldurup geri gönderir (ya da uygulamadan 'Şablonu indir')."],
    [f"• {CANIAS}: Canias'tan alınan rapor hiç düzenlenmeden gönderilir. Şablona elle kopyalanmaz. Şablon yalnız yedek / elle düzeltme içindir."],
    [f"• {KENDI}: muhasebenin kendi büyük Excel'i olduğu gibi yüklenir."],
    [""],
    ["Takip: 'İstendi' ve 'Geldi' sütunlarına Evet yazın; süzgeçle eksikleri görün."],
    ["Ayrıntılı sütun açıklamaları: sablonlar/11-16-2026-sablonlar-rehberi.pdf"],
]:
    ws3.append(satir)
ws3.column_dimensions["A"].width = 120
ws3["A1"].font = Font(bold=True)

wb.save(CIKTI)
print("yazıldı:", CIKTI.name, len(SATIRLAR), "satır,", len(TEK_SEFER), "tek seferlik")
