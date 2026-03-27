const { createApp, ref, reactive, onMounted, computed, watch } = Vue;

const API_VERSION = "1.16.1";
const CLIENT_ID = "StrmDromeWeb";

createApp({
    setup() {
        // --- State ---
        const isLoggedIn = ref(false);
        const isLoggingIn = ref(false);
        const loginError = ref("");
        const auth = reactive({ username: "", password: "", salt: "", token: "" });
        
        const currentView = ref("home"); // home, artists, albums, album_detail
        const isLoading = ref(false);
        const isScanning = ref(false);

        // Data
        const randomAlbums = ref([]);
        const recentAlbums = ref([]);
        const artistsIndex = ref([]);
        const playlists = ref([]);
        const currentAlbum = ref(null);

        // Player State
        const audioPlayer = ref(null);
        const isPlaying = ref(false);
        const currentQueue = ref([]);
        const currentIndex = ref(-1);
        const currentTime = ref(0);
        const duration = ref(0);
        const volume = ref(1);

        const currentSong = computed(() => {
            if (currentIndex.value >= 0 && currentIndex.value < currentQueue.value.length) {
                return currentQueue.value[currentIndex.value];
            }
            return null;
        });

        const progressPercent = computed(() => {
            if (!duration.value) return 0;
            return (currentTime.value / duration.value) * 100;
        });

        // --- Auth & API Helpers ---
        function getAuthParams() {
            // Using plain password for simplicity in this demo, though token is better
            return `u=${encodeURIComponent(auth.username)}&p=${encodeURIComponent(auth.password)}&v=${API_VERSION}&c=${CLIENT_ID}&f=json`;
        }

        async function apiCall(endpoint, params = "") {
            const url = `/rest/${endpoint}?${getAuthParams()}${params ? '&'+params : ''}`;
            try {
                const res = await fetch(url);
                const data = await res.json();
                if (data['subsonic-response'].status === 'failed') {
                    throw new Error(data['subsonic-response'].error.message);
                }
                return data['subsonic-response'];
            } catch (err) {
                console.error("API Error:", err);
                throw err;
            }
        }

        function getCoverUrl(id, size = 300) {
            if (!id) return 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" fill="%231a1c23"><rect width="300" height="300"/></svg>';
            return `/rest/getCoverArt?id=${id}&size=${size}&${getAuthParams()}`;
        }

        async function login() {
            isLoggingIn.value = true;
            loginError.value = "";
            try {
                await apiCall("ping");
                isLoggedIn.value = true;
                localStorage.setItem("sd_user", auth.username);
                localStorage.setItem("sd_pass", auth.password);
                loadInitialData();
            } catch (err) {
                loginError.value = err.message || "Invalid credentials.";
            } finally {
                isLoggingIn.value = false;
            }
        }

        function logout() {
            localStorage.removeItem("sd_user");
            localStorage.removeItem("sd_pass");
            isLoggedIn.value = false;
            auth.password = "";
            pausePlay();
        }

        // --- Data Fetching ---
        async function loadInitialData() {
            isLoading.value = true;
            try {
                const [randomRes, recentRes, plRes] = await Promise.all([
                    apiCall("getAlbumList2", "type=random&size=12"),
                    apiCall("getAlbumList2", "type=newest&size=12"),
                    apiCall("getPlaylists")
                ]);
                randomAlbums.value = randomRes.albumList2?.album || [];
                recentAlbums.value = randomRes.albumList2?.album?.slice().reverse() || []; // mock recent
                playlists.value = plRes.playlists?.playlist || [];
            } catch (e) { console.error(e); }
            isLoading.value = false;
        }

        async function fetchArtists() {
            isLoading.value = true;
            try {
                const res = await apiCall("getArtists");
                artistsIndex.value = res.artists?.index || [];
            } catch (e) {}
            isLoading.value = false;
        }

        async function fetchAlbums() {
            // Can be implemented similarly. For now we use Home.
        }

        async function openAlbum(id) {
            isLoading.value = true;
            try {
                const res = await apiCall("getAlbum", `id=${id}`);
                currentAlbum.value = res.album;
                currentView.value = "album_detail";
            } catch(e){}
            isLoading.value = false;
        }

        async function startScan() {
            isScanning.value = true;
            try {
                await apiCall("startScan");
                // Poll occasionally or just finish
                setTimeout(() => isScanning.value = false, 3000);
            } catch(e) { isScanning.value = false; }
        }

        // --- Playback Logic ---
        function playSong(queue, index) {
            currentQueue.value = queue;
            currentIndex.value = index;
            loadAndPlay();
        }

        function playAlbum() {
            if (!currentAlbum.value?.song?.length) return;
            playSong(currentAlbum.value.song, 0);
        }

        function loadAndPlay() {
            if (!currentSong.value) return;
            const songId = currentSong.value.id;
            const streamUrl = `/rest/stream?id=${songId}&${getAuthParams()}`;
            
            // Note: because StrmDrome returns a 302 redirect for .strm files,
            // the HTML5 audio element will automatically follow the redirect and stream the actual OpenList URL!
            audioPlayer.value.src = streamUrl;
            audioPlayer.value.play().catch(e => console.log("Autoplay blocked:", e));
            
            // Scrobble
            apiCall("scrobble", `id=${songId}&submission=true`).catch(e=>{});
        }

        function togglePlay() {
            if (!audioPlayer.value.src) {
                if (randomAlbums.value.length) openAlbum(randomAlbums.value[0].id).then(()=>playAlbum());
                return;
            }
            if (isPlaying.value) audioPlayer.value.pause();
            else audioPlayer.value.play();
        }

        function prevSong() {
            if (currentTime.value > 3) {
                audioPlayer.value.currentTime = 0;
            } else if (currentIndex.value > 0) {
                currentIndex.value--;
                loadAndPlay();
            }
        }

        function nextSong() {
            if (currentIndex.value < currentQueue.value.length - 1) {
                currentIndex.value++;
                loadAndPlay();
            } else {
                audioPlayer.value.pause();
                audioPlayer.value.currentTime = 0;
            }
        }

        // --- Audio Events ---
        function onTimeUpdate() {
            currentTime.value = audioPlayer.value.currentTime;
        }

        function onLoadedMetadata() {
            // Fallback duration if ID3 was missing
            if (!currentSong.value.duration && audioPlayer.value.duration) {
                currentSong.value.duration = audioPlayer.value.duration;
            }
            duration.value = currentSong.value.duration || audioPlayer.value.duration || 0;
        }

        function onEnded() {
            nextSong();
        }

        function seek(event) {
            if (!duration.value) return;
            const rect = event.currentTarget.getBoundingClientRect();
            const pos = (event.clientX - rect.left) / rect.width;
            audioPlayer.value.currentTime = pos * duration.value;
        }

        function seekVolume(event) {
            const rect = event.currentTarget.getBoundingClientRect();
            const pos = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
            volume.value = pos;
            audioPlayer.value.volume = pos;
        }

        // Formatting
        function formatTime(secs) {
            if (!secs) return "0:00";
            const m = Math.floor(secs / 60);
            const s = Math.floor(secs % 60);
            return `${m}:${s < 10 ? '0' : ''}${s}`;
        }
        
        function formatDuration(secs) {
            return formatTime(secs);
        }

        async function toggleStar(song) {
            const action = song.starred ? "unstar" : "star";
            try {
                await apiCall(action, `id=${song.id}`);
                song.starred = !song.starred;
            } catch(e){}
        }

        // Initialize
        onMounted(() => {
            const savedU = localStorage.getItem("sd_user");
            const savedP = localStorage.getItem("sd_pass");
            if (savedU && savedP) {
                auth.username = savedU;
                auth.password = savedP;
                login();
            }
        });

        return {
            isLoggedIn, isLoggingIn, loginError, auth, login, logout,
            currentView, isLoading, isScanning, artistsIndex,
            randomAlbums, recentAlbums, playlists, currentAlbum,
            getCoverUrl, formatTime, formatDuration, startScan,
            
            // Navigation
            fetchArtists, fetchAlbums, openAlbum,
            
            // Player
            audioPlayer, isPlaying, currentSong, currentTime, duration, progressPercent, volume,
            togglePlay, prevSong, nextSong, seek, seekVolume, playSong, playAlbum,
            onTimeUpdate, onLoadedMetadata, onEnded, toggleStar
        };
    }
}).mount('#app');
