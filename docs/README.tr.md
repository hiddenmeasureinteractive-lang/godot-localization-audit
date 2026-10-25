# Godot Localization Audit

**Yerelleştirme adaylarını bul. Küçük yamaları incele. Çeviri biçim hatalarını yakala.**

Mevcut Godot oyununu başka dillere hazırlayan geliştiriciler için yerel bir komut satırı aracı. GDScript dosyalarını okur, metinlerin neden incelenmesi gerektiğini gösterir ve açıkça seçtiğiniz görüntüleme fonksiyonları için `tr()` yamaları önerir.

Erken önizleme sürümüdür. Python 3.10+ gerekir. MIT lisanslıdır; hesap, API anahtarı veya çalışma zamanı bağımlılığı gerektirmez. Kaynak kodunu bir sunucuya göndermez.

## Kullanım

Depoyu indirdikten sonra depo klasöründe çalıştırın:

```sh
python -m godot_localization_audit scan /oyunun/klasoru
python -m godot_localization_audit scan /oyunun/klasoru --format json
python -m godot_localization_audit patch /oyunun/klasoru --display-function say
python -m godot_localization_audit check-catalog /oyunun/translations.csv
```

`scan` rapor üretir. `patch` yalnız önerilen farkı ekrana yazar; kaynak dosyalarını değiştirmez. Örneğin `say("Kapı kilitli.")` için `say(tr("Kapı kilitli."))` önerebilir. Fonksiyon metni karşılaştırıyor, anahtar olarak saklıyor veya komut olarak işliyorsa bu dönüşümü uygulamayın. Değişiklikleri inceleyin ve Godot içinde deneyin.

Godot'un mevcut POT çıkarımı ve otomatik UI çevirisi kullanılmaya devam eder. Bu araç çeviri yapmaz; tüm ekranların çevrildiğini veya davranışın korunduğunu garanti etmez. Tam bir GDScript ayrıştırıcısı değildir. Belirsiz veri akışları, çoğul biçimleri ve bağlam kararları insan incelemesi gerektirir.

Katalog denetimi için ilk sütun kaynak metni içermelidir. İlk sütunu sembolik anahtar olan dosyalar için [İngilizce belgelerdeki sınırları](../README.md) okuyun. Windows PowerShell 5.1 ile çıktı kaydederken UTF-8 kodlamasını açıkça seçin.

[İngilizce belgeler](../README.md) · [Doğrulama kapsamı](VALIDATION.md) · [Katkı rehberi](../CONTRIBUTING.md)
