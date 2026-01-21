// ==========================================
// 0. GECE MODU VE BAŞLANGIÇ AYARLARI
// ==========================================

// Türkçe karakter destekli hashtag fonksiyonu
function linkifyHashtags(text) {
    if (!text) return "";
    // XSS riskine karşı basit temizlik
    const cleanText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return cleanText.replace(/#([a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+)/g, '<a href="/explore?q=%23$1" class="hashtag-link">#$1</a>');
}

document.addEventListener('DOMContentLoaded', (event) => {
    // 1. Tema Kontrolü
    const theme = localStorage.getItem('theme');
    const btn = document.getElementById('theme-btn');

    if (theme === 'dark') {
        document.body.classList.add('dark-mode');
        if (btn) btn.innerText = '☀️';
    }

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
});

// Temayı Değiştir
function toggleDarkMode() {
    const body = document.body;
    const btn = document.getElementById('theme-btn');

    body.classList.toggle('dark-mode');

    if (body.classList.contains('dark-mode')) {
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
        projeler: [
            { ad: "Otonom İHA", resim: "projects/ieee/iha.jpg", ozet: "Teknofest 2024 Yüksek İrtifa Birincisi." },
            { ad: "Sualtı Aracı (ROV)", resim: "projects/ieee/rov.jpg", ozet: "MATE ROV Yarışması finalist aracı." }
        ]
    },
    'fark': {
        baslik: "FARK Kulübü Etkinlikleri",
        metin: "Sosyal farkındalık ve entelektüel gelişim çalışmalarımız:",
        projeler: [
            { ad: "Köy Okulları Projesi", resim: "koyokulu.jpg", ozet: "Anadolu'daki 5 okula kütüphane kurulumu." },
            { ad: "Fikir Atölyesi", resim: "atolye.jpg", ozet: "Haftalık felsefe ve sanat tartışmaları." }
        ]
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
    btn.style.backgroundColor = "#28a745";
    btn.style.borderColor = "#28a745";
    btn.style.color = "white";
    btn.style.cursor = "default";
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

async function repostPost(postId) {
    if (!confirm("Bu gönderiyi kendi profilinde yeniden paylaşmak istiyor musun?")) return;

    try {
        const response = await fetch(`/repost/${postId}`, { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            alert("Başarıyla paylaşıldı! 🔁");
            location.reload();
        } else {
            alert("Bir hata oluştu.");
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
            const icon = data.action === 'liked' ? '❤️' : '🤍';
            element.innerHTML = `${icon} <span class="like-count">${data.likes_count}</span>`;
            element.style.transform = "scale(1.3)";
            setTimeout(() => { element.style.transform = "scale(1)"; }, 200);
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
            if (data.action === 'saved') {
                element.innerHTML = '<span class="save-icon" style="color: var(--ytu-lacivert); font-weight:bold;">✅ Kaydedildi</span>';
            } else {
                element.innerHTML = '<span class="save-icon">🔖 Kaydet</span>';
            }
            element.style.transform = "scale(1.1)";
            setTimeout(() => { element.style.transform = "scale(1)"; }, 200);
        }
    } catch (error) {
        console.error('Kaydetme işleminde hata:', error);
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
    if (creator.style.display === 'none') {
        creator.style.display = 'block';
    } else {
        creator.style.display = 'none';
        document.querySelectorAll('.poll-input').forEach(i => i.value = '');
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
                document.getElementById('poll-creator').style.display = 'none';
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
    let mediaHTML = '';
    if (data.image_file) {
        if (data.is_video) {
            mediaHTML = `<div class="post-image-container"><video controls class="post-image" style="background:black;"><source src="/static/post_images/${data.image_file}" type="video/mp4"></video></div>`;
        } else {
            mediaHTML = `<div class="post-image-container"><img src="/static/post_images/${data.image_file}" class="post-image" onclick="openLightbox(this.src)"></div>`;
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

    return `
        <div class="post-header">
            <div class="post-author-info">
                <img src="/static/${data.author_pic}" class="post-avatar">
                <div>
                    <strong class="post-author-name">${data.author_name}</strong>
                    <span class="post-author-dept">${data.author_dept}</span>
                </div>
            </div>
            <small class="post-time">${data.date} <span class="badge-new" style="background:red; color:white; padding:2px 5px;">YENİ</span></small>
        </div>
        <div class="post-text">${formattedContent}</div>
        ${mediaHTML} ${pollHTML}
        <div class="post-actions">
            <span class="action-item">🤍 0</span> <span class="action-item">💬 0</span>
        </div>
        <div id="comment-box-${data.id}" class="comment-section" style="display:none;">
             <form onsubmit="submitComment(event, '${data.id}')" class="comment-form">
                <input type="text" id="comment-input-${data.id}" placeholder="Yorumun..." required class="comment-input">
                <button type="submit" class="comment-submit">Gönder</button>
            </form>
        </div>
    `;
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
    const input = document.getElementById(`comment-input-${postId}`);
    const text = input.value;
    if (!text) return;

    const formData = new FormData();
    formData.append('comment_text', text);

    try {
        const response = await fetch(`/api/add_comment/${postId}`, { method: 'POST', body: formData });
        const result = await response.json();
        if (result.success) {
            input.value = "";
            const commentBox = document.getElementById(`comment-box-${postId}`);
            const commentHTML = `<div class="comment-item"><strong class="comment-author">${result.comment.author_name}:</strong> <span class="comment-content">${result.comment.text}</span></div>`;
            const form = commentBox.querySelector('form');
            form.insertAdjacentHTML('beforebegin', commentHTML);
        } else alert(result.error);
    } catch (err) { console.error(err); }
}

// ==========================================
// 19. MESAJ GÖNDERME SİSTEMİ
// ==========================================
async function sendMessage(event) {
    if (event) event.preventDefault(); // Sayfa yenilenmesini engelle

    const input = document.getElementById('messageInput');
    const text = input.value.trim();
    const recipientId = document.getElementById('recipientId')?.value;

    if (!text || !recipientId) return;

    // 1. UI'da göster
    const myData = {
        body: text,
        sender_id: document.getElementById('currentUserId').value,
        sender_pic: document.getElementById('currentUserPic').value,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        msg_type: 'text'
    };
    appendMessageToChat(myData);
    
    input.value = "";
    const messageArea = document.getElementById("messageArea");
    messageArea.scrollTop = messageArea.scrollHeight;

    // 2. Sunucuya gönder
    try {
        const formData = new FormData();
        formData.append('body', text);
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
        }
    });

    socket.on('new_notification', (data) => {
        const notifBadge = document.querySelector('.nav-items a[href="/notifications"] .notification-badge');
        if (notifBadge) {
            let count = parseInt(notifBadge.innerText) || 0;
            notifBadge.innerText = data.count !== undefined ? data.count : count + 1;
            notifBadge.style.display = 'flex';
        }
        showToast(data.text, data.actor_pic);
    });
}

function updateInboxRow(msg) {
    const list = document.getElementById('inboxList');
    if (!list) return;

    const rowId = `conv-${msg.sender_id}`;
    let row = document.getElementById(rowId);
    let previewText = msg.msg_type === 'audio' ? '🎤 Sesli Mesaj' : msg.body;
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
        list.prepend(row);
    } else {
        const handle = msg.sender_handle || msg.sender_username || '#'; 
        const newRowHTML = `
        <a href="/chat/${handle}" class="inbox-item" id="conv-${msg.sender_id}" style="background-color: rgba(var(--ytu-lacivert-rgb), 0.05);">
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
        </a>`;
        list.insertAdjacentHTML('afterbegin', newRowHTML);
    }
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
                <img src="${imgPath}" style="width:100%; height: 280px; object-fit: cover; display:block;" onerror="this.src='/static/img/story_placeholder.jpg'">
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

// GLOBAL EVENT LISTENERS
window.addEventListener('click', function (event) {
    const modal = document.getElementById("detayModal");
    if (event.target == modal) detayKapat();
    if (!event.target.matches('.comment-menu-btn')) {
        document.querySelectorAll('.comment-dropdown').forEach(menu => { if (!menu.id.startsWith('tag-menu')) menu.style.display = 'none'; });
    }
});

// REELS SAYFASI ETKİLEŞİMLERİ
document.addEventListener('DOMContentLoaded', function () {
    if (!document.body.classList.contains('reels-mode')) return;
    const followBtns = document.querySelectorAll('.reel-follow-btn');
    followBtns.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const userId = this.dataset.userId;
            const action = this.classList.contains('following') ? 'unfollow' : 'follow';
            fetch(`/user/${userId}/${action}`, { method: 'POST' }).then(r => r.json()).then(d => {
                if (d.success) {
                    if (action === 'follow') { this.classList.add('following'); this.textContent = 'Takip Ediliyor'; }
                    else { this.classList.remove('following'); this.textContent = '+ Takip Et'; }
                }
            });
        });
    });
    const likeBtns = document.querySelectorAll('.reel-action.like-btn');
    likeBtns.forEach(btn => {
        btn.addEventListener('click', function () {
            const icon = this.querySelector('i');
            if (icon.classList.contains('fa-regular')) { icon.classList.replace('fa-regular', 'fa-solid'); }
            else { icon.classList.replace('fa-solid', 'fa-regular'); }
        });
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