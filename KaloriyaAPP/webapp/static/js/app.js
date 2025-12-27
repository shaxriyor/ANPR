/**
 * KaloriyaBot Web App JavaScript
 * Telegram Web App SDK Integration
 */

// Initialize Telegram Web App
const tg = window.Telegram?.WebApp;

// Config
const API_URL = window.location.origin;

// State
let currentUser = null;
let selectedMealType = 'lunch';

// === Telegram Web App Integration ===

function initTelegramApp() {
    if (!tg) {
        console.warn('Telegram WebApp not available, running in browser mode');
        return;
    }

    // Expand to full height
    tg.expand();

    // Set theme colors
    document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
    document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
    document.documentElement.style.setProperty('--tg-theme-link-color', tg.themeParams.link_color || '#2481cc');
    document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
    document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f0f0f0');

    // Ready callback
    tg.ready();

    console.log('Telegram WebApp initialized', tg.initDataUnsafe);
}

function getTelegramUserId() {
    if (tg?.initDataUnsafe?.user?.id) {
        return tg.initDataUnsafe.user.id;
    }
    // For browser testing
    return localStorage.getItem('test_user_id') || '123456789';
}

function closeTelegramApp() {
    if (tg) {
        tg.close();
    }
}

function showTelegramMainButton(text, callback) {
    if (tg) {
        tg.MainButton.setText(text);
        tg.MainButton.onClick(callback);
        tg.MainButton.show();
    }
}

function hideTelegramMainButton() {
    if (tg) {
        tg.MainButton.hide();
    }
}

function showTelegramBackButton(callback) {
    if (tg) {
        tg.BackButton.onClick(callback);
        tg.BackButton.show();
    }
}

function hideTelegramBackButton() {
    if (tg) {
        tg.BackButton.hide();
    }
}

function hapticFeedback(type = 'light') {
    if (tg?.HapticFeedback) {
        tg.HapticFeedback.impactOccurred(type);
    }
}

// === API Functions ===

async function apiRequest(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        },
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(`${API_URL}/api${endpoint}`, options);

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function loadUserProfile() {
    try {
        const userId = getTelegramUserId();
        currentUser = await apiRequest(`/user/${userId}`);
        return currentUser;
    } catch (error) {
        console.error('Failed to load user profile:', error);
        return null;
    }
}

async function saveUserProfile(profileData) {
    const userId = getTelegramUserId();
    return await apiRequest('/user/setup', 'POST', {
        telegram_id: userId,
        ...profileData
    });
}

async function getTodayStats() {
    const userId = getTelegramUserId();
    return await apiRequest(`/stats/today/${userId}`);
}

async function getTodayFood() {
    const userId = getTelegramUserId();
    return await apiRequest(`/food/today/${userId}`);
}

async function analyzeFood(imageBase64) {
    const userId = getTelegramUserId();
    return await apiRequest('/food/analyze', 'POST', {
        image_base64: imageBase64,
        telegram_id: userId
    });
}

async function addFoodEntry(foodData) {
    const userId = getTelegramUserId();
    return await apiRequest('/food/add', 'POST', {
        telegram_id: userId,
        ...foodData
    });
}

async function getRecommendations() {
    const userId = getTelegramUserId();
    return await apiRequest(`/stats/recommendations/${userId}`);
}

async function getWeeklyStats() {
    const userId = getTelegramUserId();
    return await apiRequest(`/stats/weekly/${userId}`);
}

async function getMealPlan() {
    const userId = getTelegramUserId();
    return await apiRequest(`/stats/meal-plan/${userId}`);
}

async function logWater(ml) {
    const userId = getTelegramUserId();
    return await apiRequest('/stats/water', 'POST', {
        telegram_id: userId,
        ml: ml
    });
}

async function logWeight(weight) {
    const userId = getTelegramUserId();
    return await apiRequest('/stats/weight', 'POST', {
        telegram_id: userId,
        weight: weight
    });
}

// === UI Functions ===

function showLoading(container, text = 'Загрузка...') {
    container.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <div class="loading-text">${text}</div>
        </div>
    `;
}

function showError(container, message) {
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">⚠️</div>
            <div class="empty-state-text">${message}</div>
        </div>
    `;
}

function showToast(message, duration = 2000) {
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function createProgressBar(current, target, className) {
    const percent = Math.min(100, Math.round((current / target) * 100));
    return `
        <div class="progress-bar">
            <div class="progress-fill ${className}" style="width: ${percent}%"></div>
        </div>
    `;
}

function formatNumber(num) {
    return Math.round(num).toLocaleString('ru-RU');
}

// === Camera Functions ===

let cameraStream = null;

async function startCamera(videoElement) {
    try {
        const constraints = {
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 }
            }
        };

        cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
        videoElement.srcObject = cameraStream;
        await videoElement.play();

        return true;
    } catch (error) {
        console.error('Camera error:', error);
        return false;
    }
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
}

function capturePhoto(videoElement) {
    const canvas = document.createElement('canvas');
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;

    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoElement, 0, 0);

    // Get base64 without data URL prefix
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
    return dataUrl.split(',')[1];
}

// === File Input Functions ===

function handleFileInput(input, callback) {
    input.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            const base64 = event.target.result.split(',')[1];
            callback(base64);
        };
        reader.readAsDataURL(file);
    });
}

// === Meal Type Selection ===

function getMealTypeEmoji(type) {
    const emojis = {
        breakfast: '🌅',
        lunch: '☀️',
        dinner: '🌆',
        snack: '🍪'
    };
    return emojis[type] || '🍽';
}

function getMealTypeName(type) {
    const names = {
        breakfast: 'Завтрак',
        lunch: 'Обед',
        dinner: 'Ужин',
        snack: 'Перекус'
    };
    return names[type] || type;
}

// === Initialize ===

document.addEventListener('DOMContentLoaded', () => {
    initTelegramApp();

    // For testing in browser
    if (!tg) {
        const testUserId = prompt('Enter test user ID:', '123456789');
        if (testUserId) {
            localStorage.setItem('test_user_id', testUserId);
        }
    }
});

// Export for use in page-specific scripts
window.KaloriyaApp = {
    getTelegramUserId,
    closeTelegramApp,
    showTelegramMainButton,
    hideTelegramMainButton,
    showTelegramBackButton,
    hideTelegramBackButton,
    hapticFeedback,
    apiRequest,
    loadUserProfile,
    saveUserProfile,
    getTodayStats,
    getTodayFood,
    analyzeFood,
    addFoodEntry,
    getRecommendations,
    getWeeklyStats,
    getMealPlan,
    logWater,
    logWeight,
    showLoading,
    showError,
    showToast,
    createProgressBar,
    formatNumber,
    startCamera,
    stopCamera,
    capturePhoto,
    handleFileInput,
    getMealTypeEmoji,
    getMealTypeName,
    currentUser,
    selectedMealType
};
