// RAWG API Integration for ChuraiGame
// Adds popular games, top-rated games, trending games, and new releases to the main page

document.addEventListener('DOMContentLoaded', async function () {
    const app = window.__vueApp;
    if (!app) return;

    // RAWG Games State
    app.config.globalProperties.$rawgGames = {
        popular: [],
        topRated: [],
        trending: [],
        newReleases: []
    };

    // Load Popular Games
    async function loadPopularGames() {
        try {
            const response = await fetch('/games/api/popular/?limit=12');
            const data = await response.json();
            return data.games || [];
        } catch (e) {
            console.error('Failed to load popular games', e);
            return [];
        }
    }

    // Load Top Rated Games
    async function loadTopRatedGames() {
        try {
            const response = await fetch('/games/api/top-rated/?limit=12');
            const data = await response.json();
            return data.games || [];
        } catch (e) {
            console.error('Failed to load top rated games', e);
            return [];
        }
    }

    // Load Trending Games
    async function loadTrendingGames() {
        try {
            const response = await fetch('/games/api/trending/?limit=10');
            const data = await response.json();
            return data.games || [];
        } catch (e) {
            console.error('Failed to load trending games', e);
            return [];
        }
    }

    // Load New Releases
    async function loadNewReleases() {
        try {
            const response = await fetch('/games/api/new-releases/?limit=8');
            const data = await response.json();
            return data.games || [];
        } catch (e) {
            console.error('Failed to load new releases', e);
            return [];
        }
    }

    // Initialize all RAWG data
    app.config.globalProperties.$rawgGames.popular = await loadPopularGames();
    app.config.globalProperties.$rawgGames.topRated = await loadTopRatedGames();
    app.config.globalProperties.$rawgGames.trending = await loadTrendingGames();
    app.config.globalProperties.$rawgGames.newReleases = await loadNewReleases();

    console.log('RAWG API data loaded successfully');
});
