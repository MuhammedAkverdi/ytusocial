// ==========================================
// 0. GECE MODU VE BAŞLANGIÇ AYARLARI
// ==========================================

// Sayfa yüklenmeden hemen çalışarak beyaz ekran (FOUC) sorununu önler
(function() {
    const theme = localStorage.getItem('theme');
    const systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (theme === 'dark' || (!theme && systemDark)) {
        document.documentElement.classList.add('dark-mode');
    }
})();

// Türkçe karakter destekli hashtag fonksiyonu
function linkifyHashtags(text) {
    if (!text) return "";
    // XSS riskine karşı basit temizlik
    const cleanText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return cleanText.replace(/#([a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+)/g, '<a href="/explore?q=%23$1" class="hashtag-link">#$1</a>');
}

document.addEventListener('DOMContentLoaded', (event) => {
    // 1. Tema Kontrolü
    const btn = document.getElementById('theme-btn');

    // Sınıf zaten html etiketine eklendi, sadece butonu güncelle
    if (document.documentElement.classList.contains('dark-mode')) {
        if (btn) btn.innerText = '☀️';
    }

    // Geçiş efektlerini sayfa yüklendikten sonra aktif et (Beyaz ekran sorununu çözer)
    setTimeout(() => {
        document.body.classList.add('transition-active');
    }, 100);

    // 2. Oylama Durumunu Kontrol Et
    const buttons = document.querySelectorAll('.btn-vote');
    buttons.forEach(btn => {
        if (btn.id && btn.id.startsWith('btn-')) {
            const id = btn.id.replace('btn-', '');
            if (localStorage.getItem('oy_verildi_' + id)) {
                oyVerildiGorseli(btn);
            }
        }
    });
    
    // 2.5 Sunucudan Güncel Oy Bilgisini Çek (LocalStorage yetersiz kalabilir)
    fetch('/api/my_votes')
        .then(response => {
            if(response.ok) return response.json();
            throw new Error('Auth error');
        })
        .then(data => {
            if (data.success) {
                data.votes.forEach(clubId => {
                    const btn = document.getElementById('btn-' + clubId);
                    if (btn) oyVerildiGorseli(btn);
                    localStorage.setItem('oy_verildi_' + clubId, 'true');
                });
            }
        })
        .catch(e => console.log("Oy bilgisi güncellenemedi (Giriş yapılmamış olabilir)"));

    // 3. Bildirimleri Otomatik Kapat (4 Saniye Sonra)
    setTimeout(() => {
        const alerts = document.querySelectorAll('.top-alert');
        alerts.forEach(alert => {
            alert.style.transition = "opacity 0.5s ease";
            alert.style.opacity = '0';
            setTimeout(() => alert.style.display = 'none', 500);
        });
    }, 4000);

    // 4. Sohbet Sayfasındaysak En Alta Kaydır
    const messageArea = document.getElementById("messageArea");
    if (messageArea) {
        messageArea.scrollTop = messageArea.scrollHeight;
    }

    // 5. Yorum Inputlarında Enter Tuşu Kontrolü
    document.querySelectorAll('.comment-input').forEach(input => {
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const form = this.closest('form');
                if (form) form.querySelector('button[type="submit"]').click();
            }
        });
    });

    // 6. Dynamic Width Initialization
    document.querySelectorAll('[data-initial-width]').forEach(el => {
        el.style.width = el.getAttribute('data-initial-width');
    });

    // 7. Chat Dosya Yukleme Butonu Entegrasyonu
    // HTML'e taşındı.

    // 8. SENKRONİZASYON İÇİN MEVCUT POSTLARA CLASS EKLEME (Server-Side Rendered)
    document.querySelectorAll('.action-item').forEach(item => {
        const onclick = item.getAttribute('onclick');
        if (!onclick) return;

        if (onclick.includes('likePost')) {
            const match = onclick.match(/likePost\('(\d+)'/);
            if (match) item.classList.add(`js-like-${match[1]}`);
        } else if (onclick.includes('savePost')) {
            const match = onclick.match(/savePost\('(\d+)'/);
            if (match) item.classList.add(`js-save-${match[1]}`);
        } else if (onclick.includes('repostPost')) {
            const match = onclick.match(/repostPost\('(\d+)'/);
            if (match) item.classList.add(`js-repost-${match[1]}`);
        }
    });

    document.querySelectorAll('form.comment-form').forEach(form => {
        const onsubmit = form.getAttribute('onsubmit');
        if (onsubmit && onsubmit.includes('submitComment')) {
            const match = onsubmit.match(/submitComment\(event, '(\d+)'\)/);
            if (match) form.classList.add(`js-comment-form-${match[1]}`);
        }
    });
});

// Temayı Değiştir
function toggleDarkMode() {
    const html = document.documentElement;
    const btn = document.getElementById('theme-btn');

    html.classList.toggle('dark-mode');

    if (html.classList.contains('dark-mode')) {
        localStorage.setItem('theme', 'dark');
        if (btn) btn.innerText = '☀️';
    } else {
        localStorage.setItem('theme', 'light');
        if (btn) btn.innerText = '🌙';
    }
}

// ==========================================
// 1. KULÜP PROJE DETAYLARI
// ==========================================
const bilgiler = {
    'ieee': {
        baslik: "IEEE YTÜ Projeleri",
        metin: "Teknoloji ve mühendislik dünyasına yön veren projelerimiz:",
        projeler: [] // Projeler geçici olarak kaldırıldı
    },
    'fark': {
        baslik: "FARK Kulübü Etkinlikleri",
        metin: "Sosyal farkındalık ve entelektüel gelişim çalışmalarımız:",
        projeler: [] // Projeler geçici olarak kaldırıldı
    },
    'girisim': {
        baslik: "Girişimcilik Kulübü",
        metin: "Geleceğin unicornlarını yetiştiren programlarımız:",
        projeler: []
    }
};

// ==========================================
// 2. DETAY PENCERESİ (MODAL) İŞLEMLERİ
// ==========================================
function detayAc(key) {
    const modal = document.getElementById("detayModal");
    const modalBaslik = document.getElementById("modalBaslik");
    const modalMetin = document.getElementById("modalMetin");

    if (!modal) return; // Modal yoksa hata verme

    const veri = bilgiler[key] || {
        baslik: "Detaylar Hazırlanıyor",
        metin: "Bu kulüp hakkında detaylı bilgi yakında eklenecektir.",
        projeler: []
    };

    modalBaslik.innerText = veri.baslik;

    let htmlIcerik = `<p class="modal-aciklama">${veri.metin}</p>`;

    if (veri.projeler && veri.projeler.length > 0) {
        htmlIcerik += `<div class="project-grid">`;
        veri.projeler.forEach(proje => {
            htmlIcerik += `
                <div class="project-item">
                    <div style="height: 120px; overflow: hidden; border-radius: 8px;">
                        <img src="/static/img/${proje.resim}" alt="${proje.ad}" 
                             style="width: 100%; height: 100%; object-fit: cover;"
                             onerror="this.src='https://via.placeholder.com/300x200?text=Gorsel+Yok'">
                    </div>
                    <div class="project-info" style="padding-top: 10px;">
                        <h4 style="color: var(--ytu-lacivert); margin-bottom: 5px;">${proje.ad}</h4>
                        <p style="font-size: 0.85rem; color: var(--text-muted);">${proje.ozet}</p>
                    </div>
                </div>
            `;
        });
        htmlIcerik += `</div>`;
    } else {
        htmlIcerik += `
            <div style="text-align: center; padding: 20px; background: var(--bg-color); border-radius: 10px; margin-top: 15px; border: 1px solid var(--border-color);">
                <span style="font-size: 2rem;">🚧</span>
                <p style="color: var(--text-muted); margin-top: 10px;">Bu kulübe ait henüz görsel proje eklenmemiş.</p>
            </div>`;
    }

    modalMetin.innerHTML = htmlIcerik;
    modal.style.display = "block";
}

function detayKapat() {
    const modal = document.getElementById("detayModal");
    if (modal) modal.style.display = "none";
}

// ==========================================
// 3. OYLAMA İŞLEMLERİ
// ==========================================
async function oyVer(kulupKey, buton) {
    if (localStorage.getItem('oy_verildi_' + kulupKey)) {
        alert("⚠️ Bu kulübe zaten oy verdiniz!");
        return;
    }

    try {
        buton.disabled = true;
        buton.innerText = "İşleniyor...";

        const response = await fetch('/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kulup: kulupKey })
        });

        if (!response.ok) {
            throw new Error(`Sunucu Hatası: ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            const sayacElementi = buton.parentElement.querySelector('.vote-count');
            if (sayacElementi) sayacElementi.innerText = result.new_vote + " Oy";
            else {
                const parentDiv = buton.closest('.club-action-area') || buton.closest('div');
                if (parentDiv) {
                    const scoreDiv = parentDiv.querySelector('div:first-child');
                    if (scoreDiv && scoreDiv.innerText.includes('Oy')) {
                        scoreDiv.innerText = result.new_vote + " Oy";
                    }
                }
            }

            localStorage.setItem('oy_verildi_' + kulupKey, 'true');
            oyVerildiGorseli(buton);
        } else {
            alert("Hata: " + (result.error || "Oylama başarısız!"));
            buton.disabled = false;
            buton.innerText = "OY VER";
        }
    } catch (error) {
        console.error("Hata Detayı:", error);
        alert("İşlem başarısız! " + error.message);
        buton.disabled = false;
        buton.innerText = "OY VER";
    }
}

function oyVerildiGorseli(btn) {
    btn.innerText = "OY VERİLDİ";
    btn.style.cursor = "default";
    btn.style.pointerEvents = "none";
    btn.disabled = true;
}

// ==========================================
// 4. POST ETKİLEŞİMLERİ
// ==========================================

function toggleComments(elementId) {
    const box = document.getElementById(elementId);
    if (box.style.display === "none") {
        box.style.display = "block";
    } else {
        box.style.display = "none";
    }
}

async function repostPost(postId, element) {
    // Butonun içindeki ikona bakarak durumu anla (Basit kontrol)
    const icon = element.querySelector('i');
    const isReposted = icon.style.color === 'rgb(46, 204, 113)' || icon.style.color === '#2ecc71';
    
    // Kullanıcı onayı
    const confirmMsg = isReposted ? "Yeniden gönderimi geri almak istiyor musun?" : "Bu gönderiyi yeniden paylaşmak istiyor musun?";
    if (!confirm(confirmMsg)) return;

    try {
        const response = await fetch(`/repost/${postId}`, { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            // Sayfadaki AYNI ID'ye sahip tüm repost butonlarını bul ve güncelle
            const allRepostBtns = document.querySelectorAll(`.js-repost-${postId}`);
            
            if (result.action === 'reposted') {
                allRepostBtns.forEach(btn => {
                    btn.innerHTML = '<i class="fa-solid fa-retweet" style="color: #2ecc71;"></i> <span style="color: #2ecc71;">Yeniden Gönderildi</span>';
                });
                
                // Sayfayı yenilemeden akışa ekle
                if (result.post) {
                    const feed = document.getElementById('feedContainer');
                    if (feed) {
                        const newPostDiv = document.createElement('div');
                        newPostDiv.className = 'post-card animate-post';
                        newPostDiv.id = `post-card-${result.post.id}`; // SİLME İŞLEMİ İÇİN ID EKLENDİ
                        newPostDiv.innerHTML = createPostHTML(result.post);
                        feed.prepend(newPostDiv);
                    }
                }
            } else {
                allRepostBtns.forEach(btn => {
                    btn.innerHTML = '<i class="fa-solid fa-retweet"></i> Yeniden Gönder';
                });
                
                // REPOST GERİ ALINDIĞINDA KARTI SAYFADAN SİL
                if (result.repost_id) {
                    const repostCard = document.getElementById(`post-card-${result.repost_id}`);
                    if (repostCard) {
                        repostCard.style.transition = "all 0.5s ease";
                        repostCard.style.opacity = "0";
                        repostCard.style.transform = "translateX(100px)";
                        setTimeout(() => repostCard.remove(), 500);
                    }
                }
            }
        } else {
            alert(result.error || "Bir hata oluştu.");
        }
    } catch (error) {
        console.error("Repost hatası:", error);
    }
}

async function likePost(postId, element) {
    try {
        const response = await fetch(`/like/${postId}`, { method: 'POST' });

        if (response.ok) {
            const data = await response.json();
            
            // Sayfadaki AYNI ID'ye sahip tüm beğeni butonlarını güncelle (Senkronizasyon)
            const allLikeBtns = document.querySelectorAll(`.js-like-${postId}`);
            const iconHtml = data.action === 'liked' ? '<i class="fa-solid fa-heart" style="color: #ff4757;"></i>' : '<i class="fa-regular fa-heart"></i>';
            
            allLikeBtns.forEach(btn => {
                btn.innerHTML = `${iconHtml} <span class="like-count">${data.likes_count}</span>`;
            });

            // Eğer beğenildiyse uçuşan kalp animasyonu ekle
            if (data.action === 'liked') {
                createFloatingHeart(element);
            }
        }
    } catch (error) {
        console.error('Beğeni işleminde hata:', error);
    }
}

async function savePost(postId, element) {
    try {
        const response = await fetch(`/save/${postId}`, { method: 'POST' });

        if (response.ok) {
            const data = await response.json();
            // Sayfadaki AYNI ID'ye sahip tüm kaydet butonlarını güncelle
            const allSaveBtns = document.querySelectorAll(`.js-save-${postId}`);
            
            if (data.action === 'saved') {
                allSaveBtns.forEach(btn => btn.innerHTML = '<span class="save-icon" style="color: var(--ytu-lacivert); font-weight:bold;"><i class="fa-solid fa-bookmark"></i> Kaydedildi</span>');
            } else {
                allSaveBtns.forEach(btn => btn.innerHTML = '<span class="save-icon"><i class="fa-regular fa-bookmark"></i> Kaydet</span>');
            }
        }
    } catch (error) {
        console.error('Kaydetme işleminde hata:', error);
    }
}

// GÖNDERİ SİLME (SAYFA YENİLEMEDEN)
async function deletePostJS(postId, element) {
    if (!confirm("Bu gönderiyi silmek istediğine emin misin?")) return;

    // Inline çağrılarda 'this' gönderilmediyse event'ten bulmaya çalış
    const targetEl = element || (window.event ? window.event.target : null);

    try {
        const response = await fetch(`/delete_post/${postId}`);
        // Backend redirect dönse bile fetch bunu takip eder, biz sonuca bakarız.
        // Ancak backend'de redirect yerine JSON dönmek daha sağlıklı olurdu.
        // Mevcut yapıda backend redirect yapıyor, bu yüzden status 200 ise siliyoruz.
        if (response.ok) {
            let postCard = document.getElementById(`post-card-${postId}`);
            
            if (!postCard && targetEl) {
                postCard = targetEl.closest('.post-card');
            }

            if (postCard) {
                postCard.style.transition = "all 0.5s ease";
                postCard.style.opacity = "0";
                postCard.style.transform = "translateX(100px)";
                setTimeout(() => postCard.remove(), 500);
                showToast("Gönderi silindi. 🗑️");
            } else {
                location.reload();
            }
        }
    } catch (error) {
        console.error("Silme hatası:", error);
    }
}

// MENÜ FONKSİYONLARI
function toggleMenu(menuId) {
    document.querySelectorAll('.comment-dropdown').forEach(menu => {
        if (menu.id !== menuId) menu.style.display = 'none';
    });

    const menu = document.getElementById(menuId);
    if (menu.style.display === 'block') {
        menu.style.display = 'none';
    } else {
        menu.style.display = 'block';
    }
}

function openEditMode(commentId) {
    document.getElementById('menu-' + commentId).style.display = 'none';
    document.getElementById('comment-text-' + commentId).style.display = 'none';
    document.getElementById('edit-form-' + commentId).style.display = 'block';
}

function closeEditMode(commentId) {
    document.getElementById('edit-form-' + commentId).style.display = 'none';
    document.getElementById('comment-text-' + commentId).style.display = 'inline';
}

function openPostEditMode(postId) {
    document.getElementById('post-menu-' + postId).style.display = 'none';
    document.getElementById('post-content-' + postId).style.display = 'none';
    document.getElementById('post-edit-form-' + postId).style.display = 'block';
}

function closePostEditMode(postId) {
    document.getElementById('post-edit-form-' + postId).style.display = 'none';
    document.getElementById('post-content-' + postId).style.display = 'block';
}

// MOBİL MENÜ
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    menu.classList.toggle('active');
}

function toggleProfileDropdown() {
    if (window.innerWidth <= 768) {
        const profileMenu = document.querySelector('.profile-menu');
        profileMenu.classList.toggle('active');
    }
}

window.addEventListener('resize', function () {
    if (window.innerWidth > 768) {
        const menu = document.getElementById('mobile-menu');
        const profileMenu = document.querySelector('.profile-menu');
        if (menu) menu.classList.remove('active');
        if (profileMenu) profileMenu.classList.remove('active');
    }
});

// LIGHTBOX
function openLightbox(src) {
    const modal = document.getElementById('lightboxModal');
    const modalImg = document.getElementById('lightboxImage');

    if (modal && modalImg) {
        modal.style.display = "flex";
        modal.style.justifyContent = "center";
        modal.style.alignItems = "center";
        modalImg.src = src;
        document.body.style.overflow = "hidden";
    }
}

function closeLightbox() {
    const modal = document.getElementById('lightboxModal');
    if (modal) {
        modal.style.display = "none";
        document.body.style.overflow = "auto";
    }
}

document.addEventListener('keydown', function (event) {
    if (event.key === "Escape") {
        closeLightbox();
        closeStory();
        detayKapat();
    }
});

// YUKARI ÇIK
const scrollBtn = document.getElementById("scrollTopBtn");
window.onscroll = function () { scrollFunction(); };

function scrollFunction() {
    if (!scrollBtn) return;
    if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) {
        scrollBtn.style.display = "block";
    } else {
        scrollBtn.style.display = "none";
    }
}

function topFunction() {
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ==========================================
// 9. STORY SİSTEMİ
// ==========================================
let currentStories = [];
let currentStoryIndex = 0;
let storyTimer;
let storyVideo;
let isStoryPaused = false;
let storyStartTime;
let storyDuration = 5000;
let remainingTime = 5000;

function openStoryGalleryWrapper(element) {
    const stories = JSON.parse(element.getAttribute('data-stories'));
    const username = element.getAttribute('data-username');
    const userPic = element.getAttribute('data-userpic');
    const isOwner = element.getAttribute('data-isowner') === 'true';
    openStoryGallery(stories, username, userPic, isOwner);
}

function openStoryGallery(stories, username, userPic, isOwner) {
    currentStories = stories;
    currentStoryIndex = 0;

    const modal = document.getElementById('storyModal');
    document.getElementById('storyUserName').innerText = username;
    document.getElementById('storyUserPic').src = userPic;
    modal.style.display = "flex";

    const progressContainer = document.getElementById('storyProgressContainer');
    progressContainer.innerHTML = '';

    stories.forEach((_, index) => {
        const barItem = document.createElement('div');
        barItem.className = 'story-progress-bar-item';
        barItem.innerHTML = `<div class="progress-fill" id="progress-${index}"></div>`;
        progressContainer.appendChild(barItem);
    });

    loadStoryItem(isOwner);
    document.addEventListener('keydown', handleStoryKeyboard);
}

function loadStoryItem(isOwner) {
    if (currentStoryIndex >= currentStories.length) {
        closeStory();
        return;
    }
    if (currentStoryIndex < 0) currentStoryIndex = 0;

    const story = currentStories[currentStoryIndex];
    const imgElement = document.getElementById('storyImage');
    const videoElement = document.getElementById('storyVideo');
    const timeElement = document.getElementById('storyTime');
    const deleteBtn = document.getElementById('deleteStoryBtn');
    const viewerBadge = document.getElementById('storyViewers');
    const viewerCount = document.getElementById('viewerCount');

    for (let i = 0; i < currentStories.length; i++) {
        const pBar = document.getElementById(`progress-${i}`);
        if (pBar) {
            pBar.style.transition = 'none';
            pBar.style.width = (i < currentStoryIndex) ? '100%' : '0%';
        }
    }

    const isVideo = story.file.match(/\.(mp4|mov|avi|webm)$/i);
    const fileUrl = `/static/story_images/${story.file}`;
    timeElement.innerText = story.timestamp;

    if (isOwner) {
        deleteBtn.style.display = 'block';
        deleteBtn.href = `/delete_story/${story.id}`;
        viewerBadge.style.display = 'block';
        viewerCount.innerText = story.viewers.length;
        viewerBadge.title = story.viewers.join(", ");
    } else {
        deleteBtn.style.display = 'none';
        viewerBadge.style.display = 'none';
        if (!story.seen) {
            fetch(`/mark_story_seen/${story.id}`, { method: 'POST' });
            story.seen = true;

            // CANLI GÜNCELLEME: Eğer tüm hikayeler izlendiyse halkayı gri yap
            const allSeen = currentStories.every(s => s.seen);
            if (allSeen) {
                const username = document.getElementById('storyUserName').innerText
                const storyItem = document.querySelector(`.story-item[data-username="${username}"]`);
                if (storyItem) {
                    const ring = storyItem.querySelector('.story-ring');
                    if (ring) {
                        ring.classList.remove('has-story-ring');
                        ring.classList.add('seen-story-ring');
                    }
                }
            }
        }
    }

    remainingTime = 5000;
    isStoryPaused = false;

    if (isVideo) {
        imgElement.style.display = "none";
        videoElement.style.display = "block";
        videoElement.src = fileUrl;
        videoElement.volume = 1.0;
        videoElement.currentTime = 0;
        videoElement.play().catch(e => console.log("Otomatik oynatma engellendi:", e));
        videoElement.onended = () => navigateStory('next');
        videoElement.onloadedmetadata = function () {
            storyDuration = videoElement.duration * 1000;
            startProgressBar(storyDuration);
        };
    } else {
        videoElement.pause();
        videoElement.style.display = "none";
        imgElement.style.display = "block";
        imgElement.src = fileUrl;
        storyDuration = 5000;
        startProgressBar(5000);
        storyStartTime = Date.now();
        storyTimer = setTimeout(() => navigateStory('next'), 5000);
    }
}

function startProgressBar(duration) {
    const pBar = document.getElementById(`progress-${currentStoryIndex}`);
    if (pBar) {
        setTimeout(() => {
            if (!isStoryPaused) {
                pBar.style.transition = `width ${duration}ms linear`;
                pBar.style.width = '100%';
            }
        }, 50);
    }
}

function navigateStory(direction) {
    clearTimeout(storyTimer);
    const pBar = document.getElementById(`progress-${currentStoryIndex}`);
    if (pBar) {
        pBar.style.transition = 'none';
        pBar.style.width = direction === 'next' ? '100%' : '0%';
    }

    if (direction === 'next') currentStoryIndex++;
    else currentStoryIndex--;

    const isOwner = document.getElementById('deleteStoryBtn').style.display === 'block';
    loadStoryItem(isOwner);
}

function pauseStory() {
    isStoryPaused = true;
    const videoElement = document.getElementById('storyVideo');
    if (videoElement.style.display !== 'none') videoElement.pause();

    clearTimeout(storyTimer);
    if (document.getElementById('storyImage').style.display !== 'none') {
        const elapsed = Date.now() - storyStartTime;
        remainingTime -= elapsed;
    }

    const pBar = document.getElementById(`progress-${currentStoryIndex}`);
    if (pBar) {
        const computedStyle = window.getComputedStyle(pBar);
        const width = computedStyle.getPropertyValue('width');
        pBar.style.transition = 'none';
        pBar.style.width = width;
    }
}

function resumeStory() {
    if (!isStoryPaused) return;
    isStoryPaused = false;

    const videoElement = document.getElementById('storyVideo');
    if (videoElement.style.display !== 'none') {
        videoElement.play();
        const remainingVideoTime = (videoElement.duration - videoElement.currentTime) * 1000;
        const pBar = document.getElementById(`progress-${currentStoryIndex}`);
        if (pBar) {
            pBar.style.transition = `width ${remainingVideoTime}ms linear`;
            pBar.style.width = '100%';
        }
    }

    if (document.getElementById('storyImage').style.display !== 'none') {
        storyStartTime = Date.now();
        storyTimer = setTimeout(() => navigateStory('next'), remainingTime);
        const pBar = document.getElementById(`progress-${currentStoryIndex}`);
        if (pBar) {
            pBar.style.transition = `width ${remainingTime}ms linear`;
            pBar.style.width = '100%';
        }
    }
}

function handleStoryKeyboard(e) {
    if (document.getElementById('storyModal').style.display === 'flex') {
        if (e.key === 'ArrowRight') navigateStory('next');
        if (e.key === 'ArrowLeft') navigateStory('prev');
        if (e.key === 'Escape') closeStory();
    }
}

function closeStory() {
    const modal = document.getElementById('storyModal');
    const videoElement = document.getElementById('storyVideo');
    if (modal) modal.style.display = "none";
    if (videoElement) {
        videoElement.pause();
        videoElement.currentTime = 0;
    }
    clearTimeout(storyTimer);
    document.removeEventListener('keydown', handleStoryKeyboard);
}

// ==========================================
// 10. ANKET SİSTEMİ
// ==========================================
function togglePollCreator() {
    const creator = document.getElementById('poll-creator');
    creator.classList.toggle('active');
    
    if (!creator.classList.contains('active')) {
        setTimeout(() => {
            document.querySelectorAll('.poll-input').forEach(i => i.value = '');
        }, 400);
    }
}

async function votePoll(pollId, optionId, element) {
    if (element.parentElement.querySelector('.poll-fill')) {
        console.log("Zaten oy verilmiş.");
        return;
    }
    try {
        const response = await fetch(`/vote_poll/${pollId}/${optionId}`, { method: 'POST' });
        const result = await response.json();
        if (result.success) location.reload();
        else alert(result.message);
    } catch (error) {
        console.error("Anket hatası:", error);
    }
}

// ==========================================
// 11. GÖRÜNTÜLÜ VE SESLİ ARAMA (WEBRTC)
// ==========================================
let localStream;
let remoteStream;
let peerConnection;
let socket;
let isCaller = false;
let incomingSignal;
let currentCallUser;
let iceCandidatesQueue = [];

const rtcSettings = {
    iceServers: [
        { urls: "stun:stun.l.google.com:19302" },
        { urls: "stun:stun1.l.google.com:19302" }
    ]
};

if (typeof io !== 'undefined') {
    socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

    socket.on('connect', () => {
        if (typeof MY_USERNAME !== 'undefined') {
            socket.emit('join', { username: MY_USERNAME });
        }
    });

    socket.on('incoming_call', (data) => {
        if (document.getElementById('callModal').style.display === 'flex') return;
        document.getElementById('incomingCallBox').style.display = 'block';
        document.getElementById('callerName').innerText = data.caller;
        document.getElementById('callType').innerText = data.isVideo ? "Görüntülü Arıyor..." : "Sesli Arıyor...";
        incomingSignal = data.signal;
        currentCallUser = data.caller;
        isCaller = false;
    });

    socket.on('call_accepted', async (signal) => {
        document.getElementById('callStatus').innerText = "Bağlanıyor...";
        try {
            await peerConnection.setRemoteDescription(new RTCSessionDescription(signal));
            processIceQueue();
        } catch (error) {
            console.error("❌ Sinyal işleme hatası:", error);
        }
    });

    socket.on('ice_candidate_msg', async (candidate) => {
        if (peerConnection && peerConnection.remoteDescription) {
            try {
                await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
            } catch (e) { console.error("❌ ICE Ekleme Hatası", e); }
        } else {
            iceCandidatesQueue.push(candidate);
        }
    });

    socket.on('call_ended', () => { closeCallModal(); });
}

async function startCall(isVideo) {
    isCaller = true;
    currentCallUser = typeof OTHER_USERNAME !== 'undefined' ? OTHER_USERNAME : null;
    
    // HATA DÜZELTME: Eğer global değişken yoksa DOM'dan al
    if (!currentCallUser) {
        const nameEl = document.querySelector('.chat-username');
        if (nameEl) currentCallUser = nameEl.innerText.trim();
    }
    
    iceCandidatesQueue = [];

    if (!currentCallUser) {
        alert("Kimi arayacağını bulamadım!");
        return;
    }

    document.getElementById('callModal').style.display = 'flex';
    const statusBox = document.getElementById('callStatus');
    statusBox.style.display = 'block';
    statusBox.innerText = "Aranıyor...";

    await setupLocalStream(isVideo);
    createPeerConnection();

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    socket.emit('call_user', {
        userToCall: currentCallUser,
        caller: MY_USERNAME,
        signal: offer,
        isVideo: isVideo
    });
}

async function acceptCall() {
    document.getElementById('incomingCallBox').style.display = 'none';
    document.getElementById('callModal').style.display = 'flex';
    document.getElementById('callStatus').innerText = "Bağlanıyor...";

    await setupLocalStream(true);
    createPeerConnection();

    await peerConnection.setRemoteDescription(new RTCSessionDescription(incomingSignal));
    processIceQueue();

    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);

    socket.emit('answer_call', {
        signal: answer,
        to: currentCallUser
    });
}

function rejectCall() {
    document.getElementById('incomingCallBox').style.display = 'none';
    socket.emit('end_call', { to: currentCallUser });
}

async function setupLocalStream(isVideo) {
    try {
        const constraints = {
            audio: true,
            video: isVideo ? { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" } : false
        };
        localStream = await navigator.mediaDevices.getUserMedia(constraints);
        document.getElementById('localVideo').srcObject = localStream;
    } catch (err) {
        console.error("❌ Kamera hatası:", err);
        alert("Kamera/Mikrofon izni gerekli.");
        closeCallModal();
    }
}

function createPeerConnection() {
    peerConnection = new RTCPeerConnection(rtcSettings);
    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });

    peerConnection.ontrack = (event) => {
        const remoteVid = document.getElementById('remoteVideo');
        if (remoteVid.srcObject !== event.streams[0]) {
            remoteVid.srcObject = event.streams[0];
            document.getElementById('callStatus').style.display = 'none';
        }
    };

    peerConnection.onicecandidate = (event) => {
        if (event.candidate) {
            socket.emit('ice_candidate', {
                candidate: event.candidate,
                to: currentCallUser
            });
        }
    };
}

async function processIceQueue() {
    while (iceCandidatesQueue.length > 0) {
        const candidate = iceCandidatesQueue.shift();
        try {
            await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (e) {}
    }
}

function endCall() {
    socket.emit('end_call', { to: currentCallUser });
    closeCallModal();
}

function closeCallModal() {
    document.getElementById('callModal').style.display = 'none';
    document.getElementById('incomingCallBox').style.display = 'none';
    if (localStream) localStream.getTracks().forEach(track => track.stop());
    if (peerConnection) peerConnection.close();
    location.reload();
}

function toggleAudio() {
    if (localStream) {
        const audioTrack = localStream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = !audioTrack.enabled;
            document.getElementById('audioBtn').innerText = audioTrack.enabled ? "🎤" : "🔇";
        }
    }
}

function toggleVideo() {
    if (localStream) {
        const videoTrack = localStream.getVideoTracks()[0];
        if (videoTrack) {
            videoTrack.enabled = !videoTrack.enabled;
            document.getElementById('videoBtn').innerText = videoTrack.enabled ? "📷" : "🚫";
        }
    }
}

// ==========================================
// 12. GELİŞMİŞ MEDYA ÖNİZLEME
// ==========================================
function previewImage(input) {
    const container = document.getElementById('image-preview');
    const previewImg = document.getElementById('preview-img');
    const previewVideo = document.getElementById('preview-video');

    if (input.files && input.files[0]) {
        var file = input.files[0];
        previewImg.style.display = 'none';
        previewVideo.style.display = 'none';
        previewVideo.src = "";

        if (file.type.startsWith('video/')) {
            previewVideo.style.display = 'block';
            previewVideo.src = URL.createObjectURL(file);
            previewVideo.load();
            container.style.display = 'block';
        } else if (file.type.startsWith('image/')) {
            var reader = new FileReader();
            reader.onload = function (e) {
                previewImg.src = e.target.result;
                previewImg.style.display = 'block';
                container.style.display = 'block';
            }
            reader.readAsDataURL(file);
        }
    }
}

function clearImage() {
    document.getElementById('file-upload').value = "";
    document.getElementById('image-preview').style.display = 'none';
    document.getElementById('preview-img').src = "";
    document.getElementById('preview-video').src = "";
}

function previewFile(input) {
    const container = document.getElementById('file-preview');
    const nameSpan = document.getElementById('preview-filename');
    if (input.files && input.files[0]) {
        nameSpan.innerText = input.files[0].name;
        container.style.display = 'block';
    }
}

function clearFile() {
    document.getElementById('doc-upload').value = "";
    document.getElementById('file-preview').style.display = 'none';
}

// ==========================================
// 13. "YAZIYOR..." İNDİKATÖRÜ
// ==========================================
let typingTimeout;
const chatInput = document.querySelector('.chat-input');

if (chatInput && typeof socket !== 'undefined') {
    chatInput.addEventListener('input', () => {
        if (typeof OTHER_USERNAME !== 'undefined') {
            socket.emit('typing', { to: OTHER_USERNAME });
            clearTimeout(typingTimeout);
            typingTimeout = setTimeout(() => {
                socket.emit('stop_typing', { to: OTHER_USERNAME });
            }, 2000);
        }
    });

    socket.on('display_typing', (data) => {
        if (typeof OTHER_USERNAME !== 'undefined' && data.username === OTHER_USERNAME) {
            const indicator = document.getElementById('typingIndicator');
            const msgArea = document.getElementById('messageArea');
            if (indicator) {
                indicator.style.display = 'block';
                msgArea.scrollTop = msgArea.scrollHeight;
            }
        }
    });

    socket.on('hide_typing', () => {
        const indicator = document.getElementById('typingIndicator');
        if (indicator) indicator.style.display = 'none';
    });
}

// Profil Sekme Değiştirme (Global Scope'a taşındı)
function switchProfileTab(tabName) {
    document.querySelectorAll('.profile-tab-content').forEach(el => el.style.display = 'none');
    const target = document.getElementById(tabName + '-content');
    if(target) target.style.display = 'block';
    
    document.querySelectorAll('.profile-tab-btn').forEach(btn => btn.classList.remove('active'));
    const btn = document.getElementById('tab-btn-' + tabName);
    if(btn) btn.classList.add('active');
}

// ==========================================
// 15. DİNAMİK SEKME BAŞLIĞI
// ==========================================
let docTitle = document.title;
window.addEventListener("focus", () => { document.title = docTitle; });

// ==========================================
// 16. SESLİ MESAJ KAYIT
// ==========================================
const recordBtn = document.getElementById('recordBtn');
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

if (recordBtn) {
    recordBtn.addEventListener('click', async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                let options = { mimeType: 'audio/webm' };
                if (!MediaRecorder.isTypeSupported('audio/webm')) options = { mimeType: 'audio/mp4' };

                mediaRecorder = new MediaRecorder(stream, options);
                mediaRecorder.start();
                isRecording = true;
                recordBtn.classList.add('recording');
                recordBtn.innerHTML = "⏹️";

                audioChunks = [];
                mediaRecorder.ondataavailable = event => audioChunks.push(event.data);

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: options.mimeType });
                    const recipientId = document.getElementById('recipientId')?.value;
                    if (!recipientId) return;

                    const formData = new FormData();
                    formData.append("audio", audioBlob, "voice_note" + (options.mimeType.includes('mp4') ? '.mp4' : '.webm'));
                    formData.append("recipient_id", recipientId);

                    try {
                        const response = await fetch('/send_audio', { method: 'POST', body: formData });
                        const result = await response.json();
                        if (result.success) appendMessageToChat(result.message);
                        else alert("Ses gönderilemedi!");
                    } catch (error) { console.error("Ses yükleme hatası:", error); }
                    stream.getTracks().forEach(track => track.stop());
                };
            } catch (err) { alert("Mikrofona erişilemedi!"); }
        } else {
            mediaRecorder.stop();
            isRecording = false;
            recordBtn.classList.remove('recording');
            recordBtn.innerHTML = "🎤";
        }
    });
}

// ==========================================
// 18. CANLI POST VE YORUM SİSTEMİ
// ==========================================
const ajaxPostForm = document.getElementById('ajaxPostForm');
if (ajaxPostForm) {
    ajaxPostForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const submitBtn = ajaxPostForm.querySelector('button[type="submit"]');
        const cardDiv = document.querySelector('.create-post-card');
        const originalBtnText = submitBtn.innerText;
        submitBtn.innerText = "Yükleniyor...";
        submitBtn.disabled = true;

        const loaderHTML = `<div id="postLoader" class="loading-overlay"><div class="spinner"></div></div>`;
        cardDiv.style.position = "relative";
        cardDiv.insertAdjacentHTML('beforeend', loaderHTML);

        const formData = new FormData(ajaxPostForm);
        try {
            const response = await fetch('/api/share_post', { method: 'POST', body: formData });
            const result = await response.json();
            if (result.success) {
                ajaxPostForm.reset();
                clearImage();
                clearFile();
                document.getElementById('poll-creator').classList.remove('active');
            } else alert("Hata: " + result.error);
        } catch (err) { alert("Sunucu hatası."); } 
        finally {
            const loader = document.getElementById('postLoader');
            if (loader) loader.remove();
            submitBtn.innerText = originalBtnText;
            submitBtn.disabled = false;
        }
    });
}

function createPostHTML(data) {
    const formattedContent = linkifyHashtags(data.content);
    const targetId = data.original_id || data.id;
    let mediaHTML = '';
    
    let repostHeader = '';
    if (data.repost_of) {
        repostHeader = `
        <div class="repost-header">
            <span>🔁</span>
            <b>${data.reposter_name}</b> yeniden gönderdi
        </div>`;
    }

    if (data.image_file) {
        const ext = data.image_file.split('.').pop().toLowerCase();
        if (['mp4', 'mov', 'avi', 'webm'].includes(ext)) {
            mediaHTML = `<div class="post-image-container"><video controls class="post-image" style="background:black;"><source src="/static/post_images/${data.image_file}" type="video/mp4"></video></div>`;
        } else if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
            mediaHTML = `<div class="post-image-container"><img src="/static/post_images/${data.image_file}" class="post-image" onclick="openLightbox(this.src)"></div>`;
        } else {
            mediaHTML = `
            <div class="post-file-container" style="margin: 10px 0;">
                <a href="/static/post_images/${data.image_file}" download class="post-file-link" style="display: flex; align-items: center; gap: 10px; padding: 15px; background: var(--bg-light); border: 1px solid var(--border-color); border-radius: 12px; text-decoration: none; color: var(--text-color); transition: 0.2s;">
                    <i class="fas fa-file-alt" style="font-size: 2rem; color: var(--ytu-lacivert);"></i>
                    <div style="flex: 1;">
                        <div style="font-weight: 600;">Dosya Eki</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted);">${data.image_file.split('_').slice(1).join('_') || data.image_file}</div>
                    </div>
                    <i class="fas fa-download" style="color: var(--text-muted);"></i>
                </a>
            </div>`;
        }
    }
    let pollHTML = '';
    if (data.has_poll) {
        let optionsHTML = '';
        data.poll_options.forEach(opt => {
            optionsHTML += `<div class="poll-option" onclick="votePoll('${data.poll_id}', '${opt.id}', this)"><div class="poll-text"><span>${opt.text}</span></div></div>`;
        });
        pollHTML = `<div class="poll-container">${optionsHTML}</div>`;
    }

    // Repost butonu durumu (Eğer kullanıcı zaten repostladıysa yeşil gelsin)
    let repostBtnHTML = `<span class="action-item js-repost-${targetId}" onclick="repostPost('${targetId}', this)"><i class="fa-solid fa-retweet"></i> Yeniden Gönder</span>`;
    
    if (data.user_has_reposted) {
        repostBtnHTML = `<span class="action-item js-repost-${targetId}" onclick="repostPost('${targetId}', this)"><i class="fa-solid fa-retweet" style="color: #2ecc71;"></i> <span style="color: #2ecc71;">Yeniden Gönderildi</span></span>`;
    }

    return `
        ${repostHeader}
        <div class="post-header">
            <div class="post-author-info">
                <img src="/static/${data.author_pic}" class="post-avatar">
                <div>
                    <strong class="post-author-name">${data.author_name}</strong>
                    <span class="post-author-dept">${data.author_dept}</span>
                </div>
            </div>
            <small class="post-time">${data.date}</small>
        </div>
        <div id="post-content-${data.id}" class="post-text">${formattedContent}</div>
        ${mediaHTML} ${pollHTML}
        
        <form action="/edit_post/${data.id}" method="POST" id="post-edit-form-${data.id}" class="edit-post-form" style="display: none;">
            <textarea name="new_content" class="create-post-input" rows="3" style="border:1px solid #ddd; border-radius:10px;">${data.content || ''}</textarea>
            <div class="edit-actions">
                <button type="button" onclick="closePostEditMode('${data.id}')" class="btn-cancel">İptal</button>
                <button type="submit" class="btn-vote btn-sm">Kaydet</button>
            </div>
        </form>

        <div class="post-actions">
            <span class="action-item js-like-${targetId}" onclick="likePost('${targetId}', this)">
                <i class="fa-regular fa-heart"></i> <span class="like-count">${data.likes_count || 0}</span>
            </span>
            <span class="action-item js-comment-count-${targetId}" onclick="toggleComments('comment-box-${data.id}')">
                <i class="fa-regular fa-comment"></i> 0
            </span>
            ${repostBtnHTML}
            <span class="action-item js-save-${targetId}" onclick="savePost('${targetId}', this)">
                <span class="save-icon"><i class="fa-regular fa-bookmark"></i> Kaydet</span>
            </span>
            
            <div class="action-menu-wrapper">
                <button type="button" class="comment-menu-btn" onclick="toggleMenu('post-menu-${data.id}')">⋮</button>
                <div id="post-menu-${data.id}" class="comment-dropdown" style="bottom: 30px; top: auto; right: 0;">
                    <button type="button" class="comment-action delete" onclick="deletePostJS('${data.id}', this)">🗑️ Sil</button>
                </div>
            </div>
        </div>

        <div id="comment-box-${data.id}" class="comment-section" style="display:none;">
             <form onsubmit="submitComment(event, '${targetId}')" class="comment-form js-comment-form-${targetId}">
                <input type="text" id="comment-input-${data.id}" placeholder="Yorumun..." required class="comment-input">
                <button type="submit" class="comment-submit">Gönder</button>
            </form>
        </div>`;
}

if (typeof socket !== 'undefined') {
    socket.on('new_global_post', function (data) {
        const feed = document.getElementById('feedContainer');
        if (feed) {
            const newPost = document.createElement('div');
            newPost.className = 'post-card animate-post';
            newPost.innerHTML = createPostHTML(data);
            feed.prepend(newPost);
        }
    });
}

async function submitComment(e, postId) {
    e.preventDefault();
    const form = e.target;
    const input = form.querySelector('input[name="comment_text"]') || form.querySelector('.comment-input');
    const text = input.value;
    if (!text) return;

    const formData = new FormData();
    formData.append('comment_text', text);

    try {
        const response = await fetch(`/api/add_comment/${postId}`, { method: 'POST', body: formData });
        const result = await response.json();
        if (result.success) {
            input.value = "";
            
            // 1. Anasayfa (Feed) İçin - TÜM KOPYALARI GÜNCELLE (Senkronizasyon)
            const allForms = document.querySelectorAll(`.js-comment-form-${postId}`);
            allForms.forEach(f => {
                const commentHTML = `<div class="comment-item"><strong class="comment-author">${result.comment.author_name}:</strong> <span class="comment-content">${result.comment.text}</span></div>`;
                f.insertAdjacentHTML('beforebegin', commentHTML);
                
                // Inputları temizle
                const fInput = f.querySelector('.comment-input');
                if(fInput) fInput.value = "";
            });

            // Yorum Sayılarını Güncelle (Senkronizasyon)
            const countSpans = document.querySelectorAll(`.js-comment-count-${postId}`);
            countSpans.forEach(span => {
                const currentText = span.innerText.trim();
                const currentCount = parseInt(currentText) || 0;
                span.innerHTML = `<i class="fa-regular fa-comment"></i> ${currentCount + 1}`;
            });

            // 2. Detay Sayfası İçin (YENİ)
            const detailComments = document.querySelector('.post-detail-comments');
            if (detailComments) {
                // Yorum metnindeki etiketleri linke çevir (Basit regex)
                let formattedText = result.comment.text.replace(/@(\w+)/g, '<a href="/u/$1" class="mention-link" style="color: var(--ytu-lacivert); font-weight: bold; text-decoration:none;">@$1</a>');
                
                const commentHTML = `
                <div class="comment-item" data-timestamp="${Date.now() / 1000}" data-likes="0">
                    <img src="/static/${result.comment.author_pic}" class="comment-avatar-sm">
                    <div class="comment-bubble" style="flex: 1;">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <strong>${result.comment.author_name}</strong>
                            <div style="position: relative;">
                                <button type="button" class="comment-menu-btn" onclick="toggleMenu('menu-${result.comment.id}')" style="position: static; padding: 0 5px; color: var(--text-muted);">⋮</button>
                                <div id="menu-${result.comment.id}" class="comment-dropdown" style="right: 0; top: 20px; width: 120px;">
                                    <button type="button" class="comment-action" onclick="openEditMode('${result.comment.id}')">✏️ Düzenle</button>
                                    <a href="/delete_comment/${result.comment.id}" class="comment-action delete" onclick="return confirm('Bu yorumu silmek istediğine emin misin?')">🗑️ Sil</a>
                                </div>
                            </div>
                        </div>
                        <p id="comment-text-${result.comment.id}" style="margin: 4px 0;">${formattedText}</p>
                        <form action="/edit_comment/${result.comment.id}" method="POST" class="edit-comment-form" id="edit-form-${result.comment.id}" style="margin-bottom: 10px;">
                            <input type="text" name="new_text" value="${result.comment.text}" class="comment-input" style="width: 100%; margin-bottom: 8px;">
                            <div style="display: flex; justify-content: flex-end; gap: 8px;">
                                <button type="button" onclick="closeEditMode('${result.comment.id}')" class="btn-cancel" style="font-size: 0.8rem;">İptal</button>
                                <button type="submit" class="btn-vote btn-sm">Kaydet</button>
                            </div>
                        </form>
                        <small class="text-muted">Şimdi</small>
                    </div>
                </div>`;
                detailComments.insertAdjacentHTML('beforeend', commentHTML);
                detailComments.scrollTop = detailComments.scrollHeight;
            }
            
        } else alert(result.error);
    } catch (err) { console.error(err); }
}

// YORUM SİLME (SAYFA YENİLEMEDEN)
async function deleteCommentJS(commentId, postId, element) {
    if (!confirm('Bu yorumu silmek istediğine emin misin?')) return;

    try {
        const response = await fetch(`/delete_comment/${commentId}`);
        const result = await response.json();

        if (result.success) {
            // 1. Yorum elementini sayfadan kaldır
            const commentItem = document.getElementById(`comment-container-${commentId}`) || element.closest('.comment-item');
            if (commentItem) {
                commentItem.style.opacity = '0';
                setTimeout(() => commentItem.remove(), 300);
            }

            // 2. Yorum sayılarını güncelle (Senkronizasyon)
            const countSpans = document.querySelectorAll(`.js-comment-count-${postId}`);
            countSpans.forEach(span => {
                const currentText = span.innerText.trim();
                const currentCount = parseInt(currentText) || 0;
                span.innerHTML = `<i class="fa-regular fa-comment"></i> ${Math.max(0, currentCount - 1)}`;
            });
        } else {
            alert(result.error || "Silinemedi.");
        }
    } catch (error) {
        console.error("Yorum silme hatası:", error);
    }
}

// ==========================================
// 19. MESAJ GÖNDERME SİSTEMİ
// ==========================================
async function sendMessage(event) {
    if (event) event.preventDefault(); // Sayfa yenilenmesini engelle

    const input = document.getElementById('messageInput');
    const fileInput = document.getElementById('chatFileInput');
    const text = input.value.trim();
    const recipientId = document.getElementById('recipientId')?.value;
    const hasFile = fileInput && fileInput.files.length > 0;

    if ((!text && !hasFile) || !recipientId) return;

    let msgType = 'text';
    let localFilePath = null;

    if (hasFile) {
        const file = fileInput.files[0];
        if (file.type.startsWith('image/')) {
            msgType = 'image';
            localFilePath = URL.createObjectURL(file);
        } else {
            msgType = 'file';
        }
    }

    // 1. UI'da göster
    const myData = {
        body: text || (hasFile ? fileInput.files[0].name : ""),
        sender_id: document.getElementById('currentUserId').value,
        sender_pic: document.getElementById('currentUserPic').value,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        msg_type: msgType,
        file_path: localFilePath,
        is_local: true
    };
    appendMessageToChat(myData);
    
    input.value = "";
    if (fileInput) fileInput.value = "";
    const messageArea = document.getElementById("messageArea");
    messageArea.scrollTop = messageArea.scrollHeight;

    // 2. Sunucuya gönder
    try {
        const formData = new FormData();
        formData.append('body', text);
        if (hasFile) {
            formData.append('file', fileInput.files[0]);
        }
        await fetch(`/send_message/${recipientId}`, { method: 'POST', body: formData });
    } catch (err) {
        console.error("Mesaj gönderilemedi:", err);
    }
}


// ==========================================
// 20. CANLI INBOX VE BİLDİRİMLER
// ==========================================
if (typeof socket !== 'undefined') {
    socket.on('receive_message', (data) => {
        const inboxList = document.getElementById('inboxList');
        if (inboxList) updateInboxRow(data);

        const messageArea = document.getElementById('messageArea');
        const recipientInput = document.getElementById('recipientId');
        
        if (messageArea && recipientInput && recipientInput.value == data.sender_id) {
            appendMessageToChat(data);
        } else {
            const msgPreview = data.msg_type === 'audio' ? '🎤 Sesli Mesaj' : data.body;
            showToast("Yeni Mesaj: " + msgPreview, data.sender_pic);
            
            // YENİ: Mesaj rozetini güncelle
            updateMessageBadge();
        }
    });

    socket.on('new_notification', (data) => {
        const badges = document.querySelectorAll('.notification-badge, .mobile-badge');
        badges.forEach(notifBadge => {
            let count = parseInt(notifBadge.innerText) || 0;
            notifBadge.innerText = data.count !== undefined ? data.count : count + 1;
            notifBadge.style.display = 'inline-block';
        });
        showToast(data.text, data.actor_pic);
    });
}

function updateInboxRow(msg) {
    const list = document.getElementById('inboxList');
    if (!list) return;

    const rowId = `conv-${msg.sender_id}`;
    let row = document.getElementById(rowId);
    let previewText = msg.msg_type === 'audio' ? '🎤 Sesli Mesaj' : (msg.msg_type === 'image' ? '📷 Resim' : (msg.msg_type === 'file' ? '📎 Dosya' : msg.body));
    if (previewText && previewText.length > 30) previewText = previewText.substring(0, 30) + "...";
    const picPath = msg.sender_pic ? `/static/${msg.sender_pic}` : '/static/img/default_avatar.png';

    if (row) {
        const lastMsgEl = row.querySelector(`#last-msg-${msg.sender_id}`);
        const timeEl = row.querySelector(`#time-${msg.sender_id}`);
        const badgeEl = row.querySelector(`#badge-${msg.sender_id}`);

        if (lastMsgEl) lastMsgEl.innerText = previewText;
        if (timeEl) timeEl.innerText = msg.timestamp;
        if (badgeEl) {
            let count = parseInt(badgeEl.innerText) || 0;
            badgeEl.innerText = count + 1;
            badgeEl.style.display = 'flex';
        }
        row.classList.add('unread-bg'); // Okunmamış stilini ekle
        
        // Parent wrapper'ı (inbox-row) bul ve en üste taşı
        const parentRow = row.closest('.inbox-row');
        if (parentRow) {
            list.prepend(parentRow);
        } else {
            list.prepend(row);
        }
    } else {
        const handle = msg.sender_handle || msg.sender_username || '#'; 
        const newRowHTML = `
        <div class="inbox-row">
        <a href="/chat/${handle}" class="inbox-item unread-bg" id="conv-${msg.sender_id}">
            <div class="avatar-wrapper"><img src="${picPath}" class="inbox-avatar" style="width: 55px; height: 55px; border-radius: 50%; object-fit: cover;"></div>
            <div class="inbox-info" style="flex: 1;">
                <div class="inbox-top-row" style="display: flex; justify-content: space-between;">
                    <span class="inbox-name" style="font-weight: 700;">${msg.sender_name || 'Kullanıcı'}</span>
                    <span class="inbox-time" id="time-${msg.sender_id}">${msg.timestamp}</span>
                </div>
                <div class="inbox-preview-row" style="display: flex; justify-content: space-between;">
                    <p class="inbox-preview" id="last-msg-${msg.sender_id}" style="font-weight:bold;">${previewText}</p>
                    <span class="unread-badge" id="badge-${msg.sender_id}" style="display: flex; background: #ff4757; color: white; padding: 2px 8px; border-radius: 10px;">1</span>
                </div>
            </div>
        </a>
        <a href="/delete_conversation/${msg.sender_id}" class="delete-conv-btn" onclick="return confirm('Bu kişiyle olan tüm mesajlaşmalar silinecek. Emin misin?');" title="Sohbeti Sil">
            <i class="fas fa-trash-alt"></i>
        </a>
        </div>`;
        list.insertAdjacentHTML('afterbegin', newRowHTML);
    }
}

// MESAJ ROZETİNİ GÜNCELLEME FONKSİYONU
function updateMessageBadge() {
    const links = document.querySelectorAll('a[href="/messages"]');
    links.forEach(link => {
        let badge = link.querySelector('.msg-badge');
        
        // Eğer badge yoksa ama span varsa (eski yapıdan kalma), onu badge yap
        if (!badge) {
            const spans = link.querySelectorAll('span');
            if (spans.length > 0 && !isNaN(parseInt(spans[spans.length - 1].innerText))) {
                badge = spans[spans.length - 1];
                badge.classList.add('msg-badge');
            }
        }
        
        if (badge) {
            let count = parseInt(badge.innerText) || 0;
            badge.innerText = count + 1;
            badge.style.display = 'inline-block';
        } else {
            badge = document.createElement('span');
            badge.className = 'msg-badge';
            badge.innerText = '1';
            link.appendChild(badge);
        }
    });
}

// SOHBETE MESAJ EKLEME FONKSİYONU (GÜNCELLENMİŞ HALİ)
function appendMessageToChat(msg) {
    const messageArea = document.getElementById('messageArea');
    if (!messageArea) return;

    const myId = document.getElementById('currentUserId').value;
    const isMe = (msg.sender_id == myId);
    
    // Mesajın sağda mı solda mı duracağını belirle
    const rowClass = isMe ? 'message-row sent' : 'message-row received';
    const bubbleClass = isMe ? 'message-bubble bubble-sent' : 'message-bubble bubble-received';

    let contentHtml = '';

    // --- 1. EĞER HİKAYE PAYLAŞIMI İSE ---
    if (msg.msg_type === 'story') {
        const storyId = msg.body;
        // Resim yolu varsa onu kullan, yoksa varsayılanı koy
        const imgPath = msg.story_img ? `/static/story_images/${msg.story_img}` : '/static/img/story_placeholder.jpg';
        
        // Tıklayınca 'viewSharedStory' fonksiyonunu çalıştıran kart yapısı
        contentHtml = `
            <div class="story-share-card" onclick="viewSharedStory(event, '${storyId}')" style="cursor:pointer; max-width: 200px; position:relative; border-radius:10px; overflow:hidden; border:1px solid rgba(255,255,255,0.2);">
                <div style="background: rgba(0,0,0,0.4); position:absolute; top:0; left:0; width:100%; height:100%; display:flex; flex-direction:column; justify-content:center; align-items:center; color:white; z-index:2;">
                    <i class="fas fa-play-circle" style="font-size: 3rem; margin-bottom:10px; opacity:0.9; text-shadow: 0 2px 10px rgba(0,0,0,0.5);"></i>
                    <span style="font-size:0.9rem; font-weight:bold; text-shadow: 0 1px 5px rgba(0,0,0,0.8);">Hikayeyi İzle</span>
                </div>
                <img src="${imgPath}" style="width:100%; height: 280px; object-fit: cover; display:block;" onerror="this.onerror=null; this.src='/static/img/default_avatar.png'">
            </div>
        `;
    } 
    // --- 2. EĞER SESLİ MESAJ İSE ---
    else if (msg.msg_type === 'audio') {
        contentHtml = `
            <audio controls controlsList="nodownload" class="audio-msg">
                <source src="/static/audio_files/${msg.file_path}" type="audio/webm">
                <source src="/static/audio_files/${msg.file_path ? msg.file_path.replace('.webm', '.mp4') : ''}" type="audio/mp4">
            </audio>`;
    } 
    // --- YENI: RESIM MESAJI ---
    else if (msg.msg_type === 'image') {
        const imgPath = (msg.is_local && msg.file_path) ? msg.file_path : `/static/message_files/${msg.file_path}`;
        contentHtml = `
            <div class="chat-image-container">
                <img src="${imgPath}" class="chat-image" onclick="openLightbox(this.src)">
            </div>`;
    }
    // --- 4. EĞER DOSYA İSE ---
    else if (msg.msg_type === 'file') {
        const fileName = msg.body;
        const downloadLink = msg.file_path ? `/static/message_files/${msg.file_path}` : '#';
        contentHtml = `
            <a href="${downloadLink}" target="_blank" class="file-msg-link">
                <i class="fas fa-file-alt file-msg-icon"></i>
                <span class="file-msg-name">${fileName}</span>
                <i class="fas fa-download file-msg-download"></i>
            </a>`;
    }
    // --- 3. EĞER NORMAL METİN İSE ---
    else {
        contentHtml = msg.body;
    }

    // Avatar Ayarı (Sadece karşı taraf için)
    let avatarHtml = '';
    if (!isMe) {
        const pic = msg.sender_pic ? msg.sender_pic : 'img/default_avatar.png';
        avatarHtml = `<img src="/static/${pic}" class="chat-avatar-sm" style="width:35px; border-radius:50%; margin-right:10px;">`;
    }

    // Silme Butonu
    const deleteLink = msg.id ? `/delete_message/${msg.id}` : '#';
    const deleteHtml = `<a href="${deleteLink}" class="msg-delete" onclick="return confirm('Silmek istediğine emin misin?');" style="margin: 0 10px; opacity: 0.5; text-decoration: none;">✕</a>`;

    // Baloncuğun stilini ayarla (Hikaye ise arka planı şeffaf yap)
    const bubbleStyle = msg.msg_type === 'story' ? 'padding:0; background:none; border:none; box-shadow:none;' : '';

    const html = `
    <div class="${rowClass}">
        ${!isMe ? avatarHtml : ''} 
        ${isMe ? deleteHtml : ''}
        
        <div class="${bubbleClass}" style="${bubbleStyle}">
            ${contentHtml}
            
            ${msg.msg_type !== 'story' ? 
                `<span class="msg-time" style="display:flex; align-items:center; gap:3px; justify-content:flex-end;">
                    ${msg.timestamp} 
                    ${isMe ? '<i class="fas fa-check"></i>' : ''}
                </span>` 
            : ''}
        </div>
    </div>`;

    // Ekrana Basma İşlemi
    const typingDiv = document.getElementById('typingIndicator');
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;

    if (typingDiv && typingDiv.parentNode === messageArea) {
        messageArea.insertBefore(tempDiv.firstElementChild, typingDiv);
    } else {
        messageArea.appendChild(tempDiv.firstElementChild);
    }

    // En alta kaydır
    messageArea.scrollTop = messageArea.scrollHeight;
}

function showToast(text, img) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = "position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;";
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.style.cssText = "background: var(--card-bg, #fff); color: var(--text-color, #333); box-shadow: 0 5px 15px rgba(0,0,0,0.2); padding: 15px; border-left: 4px solid #003366; display: flex; align-items: center; gap: 10px; border-radius: 10px; cursor: pointer;";
    const imgSrc = img ? `/static/${img}` : '/static/img/default_avatar.png';
    toast.innerHTML = `<img src="${imgSrc}" style="width: 35px; border-radius: 50%;"><span>${text}</span>`;
    toast.onclick = () => window.location.href = '/messages';
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ==========================================
// 21. ONLINE DURUM TAKİBİ
// ==========================================
if (typeof socket !== 'undefined') {
    socket.on('user_status_change', (data) => {
        const dot = document.getElementById(`status-dot-${data.user_id}`);
        if (dot) data.status === 'online' ? dot.classList.add('online') : dot.classList.remove('online');

        const recipientInput = document.getElementById('recipientId');
        if (recipientInput && recipientInput.value == data.user_id) {
            const statusText = document.getElementById('user-status-text');
            if (statusText) statusText.innerHTML = data.status === 'online' ? '<span style="color: #2ecc71;">● Çevrimiçi</span>' : 'Çevrimdışı';
        }
    });
}

// GERİ BİLDİRİM MODALI
function openFeedbackModal() {
    document.getElementById('feedbackModal').style.display = 'block';
}
function closeFeedbackModal() {
    document.getElementById('feedbackModal').style.display = 'none';
}

// GLOBAL EVENT LISTENERS
window.addEventListener('click', function (event) {
    const modal = document.getElementById("detayModal");
    if (event.target == modal) detayKapat();
    if (!event.target.matches('.comment-menu-btn')) {
        document.querySelectorAll('.comment-dropdown').forEach(menu => { if (!menu.id.startsWith('tag-menu')) menu.style.display = 'none'; });
    }
    if (event.target == document.getElementById('feedbackModal')) closeFeedbackModal();
});

// REELS SAYFASI ETKİLEŞİMLERİ
document.addEventListener('DOMContentLoaded', function () {
    if (!document.body.classList.contains('reels-mode')) return;
    const followBtns = document.querySelectorAll('.reel-follow-btn');
    followBtns.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const userId = this.dataset.userId;
            
            fetch(`/api/follow_user/${userId}`, { method: 'POST' }).then(r => r.json()).then(d => {
                if (d.success) {
                    if (d.action === 'followed') { 
                        // Animasyonlu Tik İşareti
                        this.innerHTML = '<i class="fas fa-check"></i>';
                        this.classList.add('followed-success');
                        setTimeout(() => {
                            this.style.opacity = '0';
                            setTimeout(() => this.style.display = 'none', 500);
                        }, 1000);
                    }
                }
            });
        });
    });

    // 2. Beğeni Butonları (Görsel Toggle)
    const likeBtns = document.querySelectorAll('.reel-action.like-btn');
    likeBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const icon = this.querySelector('i');
            if (icon.classList.contains('fa-regular')) { 
                icon.classList.replace('fa-regular', 'fa-solid'); 
                icon.style.color = '#ff4757'; // Kırmızı
            } else { 
                icon.classList.replace('fa-solid', 'fa-regular'); 
                icon.style.color = 'white'; // Beyaz
            }
        });
    });

    // 3. Otomatik Oynatma ve Durdurma (Intersection Observer)
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const video = entry.target.querySelector('video');
            if (!video) return;

            if (entry.isIntersecting) {
                video.play().catch(e => console.log("Otomatik oynatma engellendi:", e));
            } else {
                video.pause();
            }
        });
    }, { threshold: 0.6 }); // %60'ı görünüyorsa oynat

    document.querySelectorAll('.reel-item').forEach(item => {
        observer.observe(item);

        // 4. Çift Tıklama ile Beğeni (Instagram Tarzı)
        item.addEventListener('dblclick', function(e) {
            const likeBtn = this.querySelector('.reel-action.like-btn');
            if (likeBtn) {
                showReelsHeart(e.clientX, e.clientY); // Animasyon
                
                // Eğer beğenilmemişse beğen (İkon kontrolü)
                const icon = likeBtn.querySelector('i');
                if (icon && icon.classList.contains('fa-regular')) {
                    likeBtn.click();
                }
            }
        });

        // 5. Tek Tıklama ile Oynat/Durdur
        item.addEventListener('click', function(e) {
            // Eğer tıklanan yer butonlar veya interaktif elemanlar değilse işlem yapma
            if (e.target.closest('.reel-sidebar') || e.target.closest('.reel-info') || e.target.closest('.reels-back-btn')) return;

            const video = this.querySelector('video');
            if (video) {
                if (video.paused) {
                    video.play().catch(err => console.log("Oynatma hatası:", err));
                } else {
                    video.pause();
                }
            }
        });
    });

    // Klavye ile Reels Kaydırma (Yumuşak Geçiş)
    document.addEventListener('keydown', function(e) {
        const container = document.querySelector('.reels-container');
        if (!container) return;

        const itemHeight = window.innerHeight;
        const currentScroll = container.scrollTop;
        const index = Math.round(currentScroll / itemHeight);

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            container.scrollTo({
                top: (index + 1) * itemHeight,
                behavior: 'smooth'
            });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            container.scrollTo({
                top: (index - 1) * itemHeight,
                behavior: 'smooth'
            });
        }
    });
});

// ==========================================
// 22. GELİŞMİŞ PAYLAŞIM SİSTEMİ (GÜNCELLENDİ)
// ==========================================

let globalShareLink = "";
let globalShareTitle = "Bu harika gönderiye bak!";
let usersLoaded = false; 

// Global Type ve ID saklayıcılar
window.currentShareType = "";
window.currentShareId = null;

// Modalı Aç
function openShareModal(type, id) {
    const modal = document.getElementById('advancedShareModal');
    if(!modal) return;

    // Verileri global değişkenlere kaydet (EN ÖNEMLİ KISIM)
    window.currentShareType = type;
    window.currentShareId = id;

    // Linki Oluştur
    const baseUrl = window.location.origin;
    if (type === 'story') {
        globalShareLink = `${baseUrl}/s/${id}`;
        globalShareTitle = "YTU Social'da bu hikayeye bak!";
    } else {
        globalShareLink = `${baseUrl}/p/${id}`;
        globalShareTitle = "YTU Social'da bu gönderiye bak!";
    }

    modal.style.display = 'flex';

    if (!usersLoaded) {
        loadShareUsers();
    }
}

// Modalı Kapat
function closeAdvancedShare() {
    document.getElementById('advancedShareModal').style.display = 'none';
    document.getElementById('shareSearchInput').value = "";
    filterShareUsers(); 
}

// Kullanıcıları API'den Çek
async function loadShareUsers() {
    const listContainer = document.getElementById('shareUserListContainer');
    
    try {
        const response = await fetch('/api/get_share_users');
        const data = await response.json();

        if (data.success) {
            listContainer.innerHTML = "";
            data.users.forEach(user => {
                const userHtml = `
                <div class="share-user-item" data-username="${user.username.toLowerCase()}">
                    <div class="share-user-info">
                        <img src="/static/${user.profile_pic}" class="share-avatar">
                        <div>
                            <div style="font-weight: 600; color: var(--text-color);">${user.username}</div>
                            <div style="font-size: 0.8rem; color: var(--text-muted);">${user.department || ''}</div>
                        </div>
                    </div>
                    <button class="share-btn-send" onclick="sendShareToDM(this, ${user.id})">Gönder</button>
                </div>
                `;
                listContainer.insertAdjacentHTML('beforeend', userHtml);
            });
            usersLoaded = true;
        } else {
            listContainer.innerHTML = "<p style='text-align:center'>Kullanıcılar yüklenemedi.</p>";
        }
    } catch (err) {
        console.error("Kullanıcı yükleme hatası:", err);
    }
}

// DM Olarak Gönder (GÜNCELLENMİŞ: HİKAYE TESPİTİ YAPAR)
async function sendShareToDM(btn, userId) {
    btn.innerText = "Gönderiliyor...";
    btn.disabled = true;

    const formData = new FormData();
    
    // EĞER HİKAYE İSE: story_id GÖNDER
    if (window.currentShareType === 'story') {
        formData.append('story_id', window.currentShareId);
        formData.append('body', 'Hikaye Paylaşımı'); 
    } 
    // DEĞİLSE: LİNK GÖNDER
    else {
        formData.append('body', `Buna bir bak: ${globalShareLink}`);
    }

    try {
        const response = await fetch(`/send_message/${userId}`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();

        if (result.success) {
            btn.innerText = "Gönderildi";
            btn.classList.add('sent');
            showToast("Mesaj gönderildi! ✅");
        } else {
            btn.innerText = "Hata";
            btn.disabled = false;
        }
    } catch (err) {
        console.error(err);
        btn.innerText = "Hata";
    }
}

// Arama Filtreleme
function filterShareUsers() {
    const input = document.getElementById('shareSearchInput').value.toLowerCase();
    const items = document.querySelectorAll('.share-user-item');

    items.forEach(item => {
        const username = item.getAttribute('data-username');
        if (username.includes(input)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function scrollToNextReel(element) {
    const currentReel = element.closest('.reel-item');
    const nextReel = currentReel.nextElementSibling;
    if (nextReel) {
        nextReel.scrollIntoView({ behavior: 'smooth' });
    }
}

// Bağlantıyı Kopyala
function copyShareLinkPro() {
    navigator.clipboard.writeText(globalShareLink).then(() => {
        showToast("Bağlantı kopyalandı! 📋");
        closeAdvancedShare();
    }).catch(err => {
        alert("Kopyalanamadı: " + globalShareLink);
    });
}

// Dış Uygulamalarda Paylaş
function shareExternal(app) {
    let url = "";
    const text = encodeURIComponent(globalShareTitle);
    const link = encodeURIComponent(globalShareLink);

    if (app === 'whatsapp') {
        url = `https://api.whatsapp.com/send?text=${text}%20${link}`;
    } else if (app === 'twitter') {
        url = `https://twitter.com/intent/tweet?text=${text}&url=${link}`;
    } else if (app === 'telegram') {
        url = `https://t.me/share/url?url=${link}&text=${text}`;
    }

    window.open(url, '_blank');
}

// Dışarı tıklayınca kapat
window.onclick = function(event) {
    const modal = document.getElementById('advancedShareModal');
    if (event.target === modal) {
        closeAdvancedShare();
    }
}

// ==========================================
// 23. HİKAYE PAYLAŞMA FONKSİYONU
// ==========================================

function shareActiveStory() {
    // Global değişkenler: currentStories ve currentStoryIndex
    if (typeof currentStories !== 'undefined' && currentStories.length > 0) {
        
        // Hata önleyici: Eğer index kaymışsa düzelt
        if (currentStoryIndex < 0) currentStoryIndex = 0;
        if (currentStoryIndex >= currentStories.length) currentStoryIndex = currentStories.length - 1;

        const storyId = currentStories[currentStoryIndex].id;
        
        // Modal'ı aç (Advanced Share Modal)
        openShareModal('story', storyId);
        
        // Paylaşım yaparken hikayeyi duraklat (Video ise durur, süre işlemez)
        pauseStory();
        
    } else {
        console.log("Paylaşılacak aktif hikaye bulunamadı.");
    }
}

// ==========================================
// 24. SOHBETTEN HİKAYE İZLEME (MODAL)
// ==========================================
async function viewSharedStory(event, storyId) {
    event.preventDefault(); // Sayfa yönlendirmesini durdur

    try {
        const response = await fetch(`/api/get_story/${storyId}`);
        const data = await response.json();

        if (data.success) {
            // Mevcut hikaye oynatıcısını kullanmak için veriyi hazırlıyoruz
            // openStoryGallery fonksiyonu bir dizi (array) bekler
            const storiesArray = [data.story]; 
            
            // Story Modalı'nı açan fonksiyonu çağırıyoruz (Zaten yazmıştık)
            openStoryGallery(
                storiesArray, 
                data.user.username, 
                "/static/" + data.user.profile_pic, 
                data.user.is_owner
            );
            
        } else {
            alert("Bu hikaye artık mevcut değil.");
        }
    } catch (err) {
        console.error("Hikaye açma hatası:", err);
    }
}

// ==========================================
// 25. UÇUŞAN KALP ANİMASYONU
// ==========================================
function createFloatingHeart(element) {
    const heart = document.createElement('div');
    heart.innerText = '❤️';
    heart.classList.add('floating-heart');
    
    const rect = element.getBoundingClientRect();
    heart.style.left = (rect.left + window.scrollX + rect.width / 2) + 'px';
    heart.style.top = (rect.top + window.scrollY) + 'px';
    
    document.body.appendChild(heart);
    
    setTimeout(() => {
        heart.remove();
    }, 1000);
}

// Reels İçin Özel Büyük Kalp Animasyonu
function showReelsHeart(x, y) {
    const heart = document.createElement('i');
    heart.className = 'fas fa-heart';
    heart.style.position = 'fixed';
    heart.style.left = x + 'px';
    heart.style.top = y + 'px';
    heart.style.transform = 'translate(-50%, -50%) scale(0)';
    heart.style.color = 'white';
    heart.style.fontSize = '6rem';
    heart.style.zIndex = '9999';
    heart.style.pointerEvents = 'none';
    heart.style.textShadow = '0 10px 20px rgba(0,0,0,0.3)';
    heart.style.transition = 'transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.2s ease-in';
    
    document.body.appendChild(heart);
    
    requestAnimationFrame(() => { heart.style.transform = 'translate(-50%, -50%) scale(1)'; });
    
    setTimeout(() => {
        heart.style.opacity = '0';
        heart.style.transform = 'translate(-50%, -50%) scale(1.2)';
        setTimeout(() => heart.remove(), 300);
    }, 800);
}

// ==========================================
// 26. REELS YORUM SİSTEMİ (BOTTOM SHEET)
// ==========================================
async function openReelComments(postId) {
    const modal = document.getElementById('reelCommentModal');
    const list = document.getElementById('reelCommentsList');
    const inputId = document.getElementById('currentReelId');
    
    if(!modal || !list) return;

    inputId.value = postId;
    list.innerHTML = '<div style="text-align:center; padding:20px; color:#aaa;">Yükleniyor...</div>';
    modal.style.display = 'flex';

    try {
        const response = await fetch(`/api/get_comments/${postId}`);
        const data = await response.json();

        if(data.success) {
            list.innerHTML = '';
            if(data.comments.length === 0) {
                list.innerHTML = '<div style="text-align:center; padding:20px; color:#aaa;">Henüz yorum yok. İlk yorumu sen yap!</div>';
            } else {
                data.comments.forEach(comment => {
                    const html = `
                        <div class="reel-comment-item">
                            <img src="/static/${comment.author_pic}" class="reel-comment-avatar">
                            <div>
                                <div style="font-weight:bold; font-size:0.9rem;">${comment.author_name} <span style="font-weight:normal; color:#aaa; font-size:0.75rem; margin-left:5px;">${comment.timestamp}</span></div>
                                <div style="color:#ddd;">${comment.text}</div>
                            </div>
                        </div>
                    `;
                    list.insertAdjacentHTML('beforeend', html);
                });
            }
            // En alta kaydır
            list.scrollTop = list.scrollHeight;
        }
    } catch(e) {
        console.error(e);
        list.innerHTML = '<div style="text-align:center; color:red;">Yorumlar yüklenemedi.</div>';
    }
}

function closeReelComments() {
    document.getElementById('reelCommentModal').style.display = 'none';
}

async function submitReelComment(event) {
    event.preventDefault();
    const postId = document.getElementById('currentReelId').value;
    const input = document.getElementById('reelCommentInput');
    const text = input.value.trim();
    
    if(!text) return;

    const formData = new FormData();
    formData.append('comment_text', text);

    try {
        const response = await fetch(`/api/add_comment/${postId}`, { method: 'POST', body: formData });
        const result = await response.json();

        if(result.success) {
            input.value = '';
            const list = document.getElementById('reelCommentsList');
            
            // "Henüz yorum yok" yazısını kaldır
            if(list.innerText.includes('Henüz yorum yok')) list.innerHTML = '';

            const html = `
                <div class="reel-comment-item animate-post">
                    <img src="/static/${result.comment.author_pic}" class="reel-comment-avatar">
                    <div>
                        <div style="font-weight:bold; font-size:0.9rem;">${result.comment.author_name} <span style="font-weight:normal; color:#aaa; font-size:0.75rem; margin-left:5px;">Şimdi</span></div>
                        <div style="color:#ddd;">${result.comment.text}</div>
                    </div>
                </div>
            `;
            list.insertAdjacentHTML('beforeend', html);
            list.scrollTop = list.scrollHeight;

            // Sağ menüdeki yorum sayısını güncelle
            const countSpan = document.getElementById(`reel-comment-count-${postId}`);
            if(countSpan) {
                countSpan.innerText = parseInt(countSpan.innerText) + 1;
            }
        }
    } catch(e) {
        console.error(e);
    }
}

// ==========================================
// 27. YORUM SIRALAMA VE ETİKETLEME
// ==========================================

// Yorumları Sırala
function sortComments(order) {
    const container = document.getElementById('commentsContainer');
    if (!container) return;

    // Sadece yorum olanları al (açıklama kısmı hariç)
    const items = Array.from(container.querySelectorAll('.comment-item[data-timestamp]'));
    
    items.sort((a, b) => {
        const timeA = parseFloat(a.getAttribute('data-timestamp'));
        const timeB = parseFloat(b.getAttribute('data-timestamp'));
        const likeA = parseInt(a.getAttribute('data-likes')) || 0;
        const likeB = parseInt(b.getAttribute('data-likes')) || 0;

        if (order === 'newest') return timeB - timeA;
        if (order === 'oldest') return timeA - timeB;
        if (order === 'popular') return likeB - likeA;
    });

    // Mevcut yorumları geçici olarak kaldır ve sıralı ekle
    items.forEach(item => item.remove());
    items.forEach(item => container.appendChild(item));
}

// Sayfa yüklendiğinde varsayılan olarak "En Yeniler" yap
document.addEventListener('DOMContentLoaded', () => {
    if(document.getElementById('commentsContainer')) {
        sortComments('newest');
    }
    // Initialize mention system on all pages (will bind to any inputs present)
    setupMentionSystem();
});

// Etiketleme Sistemi (@username)
function setupMentionSystem() {
    // Create a single floating suggestion box if not present
    let suggestionBox = document.getElementById('mention-suggestions-global');
    if (!suggestionBox) {
        suggestionBox = document.createElement('div');
        suggestionBox.id = 'mention-suggestions-global';
        suggestionBox.className = 'mention-dropdown';
        suggestionBox.style.position = 'absolute';
        suggestionBox.style.display = 'none';
        suggestionBox.style.zIndex = 99999;
        document.body.appendChild(suggestionBox);
    }

    const DEBOUNCE_MS = 260;
    function debounce(fn, wait) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn(...args), wait);
        };
    }

    // Attach mention handlers to an input/textarea
    function bindInput(input) {
        if (input._mentionBound) return;
        input._mentionBound = true;

        let currentItems = [];
        let selectedIndex = -1;

        async function fetchAndShow(query, caretRect) {
            try {
                const res = await fetch(`/api/search_users?q=${encodeURIComponent(query)}`);
                if (!res.ok) throw new Error('Network');
                const data = await res.json();
                if (!data.success || !data.users || data.users.length === 0) {
                    suggestionBox.style.display = 'none';
                    return;
                }

                suggestionBox.innerHTML = '';
                currentItems = data.users;
                selectedIndex = -1;

                data.users.forEach((user, idx) => {
                    const div = document.createElement('div');
                    div.className = 'mention-item';
                    div.dataset.index = idx;
                    div.innerHTML = `
                        <img src="/static/${user.profile_pic}" class="mention-avatar">
                        <div class="mention-info">
                            <span class="mention-name">${user.username}</span>
                            <span class="mention-handle">@${user.handle}</span>
                        </div>`;
                    div.addEventListener('mousedown', (ev) => {
                        // use mousedown to avoid blur before click
                        ev.preventDefault();
                        applySelection(input, user);
                    });
                    suggestionBox.appendChild(div);
                });

                // Position suggestion box under input caret (approx)
                if (caretRect) {
                    suggestionBox.style.left = (window.scrollX + caretRect.left) + 'px';
                    suggestionBox.style.top = (window.scrollY + caretRect.bottom + 6) + 'px';
                    suggestionBox.style.minWidth = Math.max(220, caretRect.width) + 'px';
                } else {
                    const rect = input.getBoundingClientRect();
                    suggestionBox.style.left = (window.scrollX + rect.left) + 'px';
                    suggestionBox.style.top = (window.scrollY + rect.bottom + 6) + 'px';
                    suggestionBox.style.minWidth = Math.max(220, rect.width) + 'px';
                }

                suggestionBox.style.display = 'block';
            } catch (e) {
                console.error('Mention fetch error', e);
                suggestionBox.style.display = 'none';
            }
        }

        const debouncedFetch = debounce(fetchAndShow, DEBOUNCE_MS);

        function getCaretCoordinates(el, position) {
            // Best-effort: use range on textarea/input via mirror div fallback
            try {
                if (el.selectionEnd !== undefined) {
                    // For inputs/textareas, approximate using getBoundingClientRect of input
                    const rect = el.getBoundingClientRect();
                    return { left: rect.left + 8, bottom: rect.top + rect.height, width: rect.width };
                }
            } catch (e) {}
            return null;
        }

        function applySelection(inputEl, user) {
            const val = inputEl.value;
            const cursor = inputEl.selectionStart || val.length;
            const textBeforeCursor = val.substring(0, cursor);
            const match = textBeforeCursor.match(/(^|\s)@([\wğüşöçıİĞÜŞÖÇ-]+)$/i);
            if (!match) return;
            const prefix = textBeforeCursor.substring(0, match.index + match[1].length);
            const newText = prefix + '@' + user.handle + ' ' + val.substring(cursor);
            inputEl.value = newText;
            // move caret after inserted handle + space
            const newPos = (prefix + '@' + user.handle + ' ').length;
            inputEl.setSelectionRange(newPos, newPos);
            suggestionBox.style.display = 'none';
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            inputEl.focus();
        }

        input.addEventListener('keydown', (e) => {
            if (suggestionBox.style.display === 'block') {
                const items = suggestionBox.querySelectorAll('.mention-item');
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
                    items.forEach((it, i) => it.classList.toggle('selected', i === selectedIndex));
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    selectedIndex = Math.max(selectedIndex - 1, 0);
                    items.forEach((it, i) => it.classList.toggle('selected', i === selectedIndex));
                } else if (e.key === 'Enter') {
                    if (selectedIndex >= 0 && items[selectedIndex]) {
                        e.preventDefault();
                        const u = currentItems[selectedIndex];
                        applySelection(input, u);
                    }
                } else if (e.key === 'Escape') {
                    suggestionBox.style.display = 'none';
                }
            }
        });

        input.addEventListener('input', function () {
            const val = this.value;
            const cursor = this.selectionStart;
            const textBeforeCursor = val.substring(0, cursor);
            const m = textBeforeCursor.match(/(^|\s)@([\wğüşöçıİĞÜŞÖÇ-]{1,})$/i);
            if (m) {
                const query = m[2];
                const caretRect = getCaretCoordinates(this, cursor);
                debouncedFetch(query, caretRect);
            } else {
                suggestionBox.style.display = 'none';
            }
        });

        // Hide suggestions on blur (small delay to allow click)
        input.addEventListener('blur', () => setTimeout(() => suggestionBox.style.display = 'none', 120));
    }

    // Bind existing and future inputs
    function bindAll() {
        document.querySelectorAll('.detail-comment-input, .comment-input, input[data-mention], textarea[data-mention]').forEach(bindInput);
    }

    bindAll();

    // Watch for dynamically added comment inputs
    const mo = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.addedNodes && m.addedNodes.length) {
                m.addedNodes.forEach(node => {
                    if (node.querySelectorAll) {
                        node.querySelectorAll('.detail-comment-input, .comment-input, input[data-mention], textarea[data-mention]').forEach(bindInput);
                    }
                    if (node.classList && (node.classList.contains('detail-comment-input') || node.classList.contains('comment-input'))) {
                        bindInput(node);
                    }
                });
            }
        }
    });
    mo.observe(document.body, { childList: true, subtree: true });

    // Global click to hide when clicking outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.mention-item') && !e.target.closest('.detail-comment-input') && !e.target.closest('.comment-input')) {
            suggestionBox.style.display = 'none';
        }
    });
}

// ==========================================
// 28. KULÜP TAKİP VE OYLAMA (AJAX)
// ==========================================
async function toggleClubFollow(clubId, btn) {
    try {
        const response = await fetch(`/follow_club/${clubId}`);
        const data = await response.json();
        
        if (data.success) {
            const countSpan = document.querySelector('.c-meta span:first-child');
            if (data.action === 'followed') {
                btn.classList.add('active');
                btn.innerHTML = '<i class="fas fa-check"></i> Takip Ediliyor';
            } else {
                btn.classList.remove('active');
                btn.innerHTML = '<i class="fas fa-plus"></i> Takip Et';
            }
            if(countSpan) countSpan.innerHTML = `<i class="fas fa-users"></i> ${data.count} Takipçi`;
        }
    } catch (error) {
        console.error('Takip hatası:', error);
    }
}

async function voteClub(clubId, btn) {
    if (btn.disabled) return;
    
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i>';
    
    try {
        const response = await fetch(`/vote_club/${clubId}`);
        const data = await response.json();
        
        if (data.success) {
            btn.innerHTML = '<i class="fas fa-check"></i> Oy Verildi';
            btn.style.backgroundColor = '#28a745';
            btn.style.transform = 'scale(1.1)';
            setTimeout(() => btn.style.transform = 'scale(1)', 200);
            btn.disabled = true;
            btn.style.cursor = 'default';
            
            const countSpan = document.querySelector('.c-meta span:last-child');
            if(countSpan) countSpan.innerHTML = `<i class="fas fa-trophy"></i> ${data.new_total} Lig Puanı`;
            
            // Uçuşan kalp animasyonu
            if (typeof createFloatingHeart === 'function') {
                createFloatingHeart(btn);
            }
        } else {
            btn.innerHTML = originalContent;
            alert(data.message);
        }
    } catch (error) {
        console.error('Oylama hatası:', error);
        btn.innerHTML = originalContent;
    }
}