
export async function fetchStats() {
    try {
        const response = await fetch('/data/stats.json');
        if (!response.ok) {
            throw new Error('Failed to fetch stats');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

export function formatStatName(name) {
    return name
        .split("_")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
}
