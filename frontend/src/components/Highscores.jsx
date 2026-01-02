import React, { useState, useEffect } from 'react';
import { api } from '../api';
import './Highscores.css';

const Highscores = () => {
    const [scores, setScores] = useState({});
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchScores = async () => {
            try {
                const data = await api.getModelScores();
                setScores(data);
            } catch (error) {
                console.error('Failed to fetch highscores:', error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchScores();
    }, []);

    if (isLoading) {
        return <div className="highscores-loading">Loading Council Stats...</div>;
    }

    // Sort scores desc
    const sortedScores = Object.entries(scores)
        .sort(([, scoreA], [, scoreB]) => scoreB - scoreA);

    if (sortedScores.length === 0) {
        return null; // Don't show if no scores yet
    }

    // Calculate ranks with tie handling
    let currentRank = 1;
    const rankedList = sortedScores.map(([model, score], index) => {
        if (index > 0 && score < sortedScores[index - 1][1]) {
            currentRank = index + 1;
        }
        return { model, score, rank: currentRank };
    });

    // Determine if rank 1 is unique (strictly ahead)
    const rank1Count = rankedList.filter(item => item.rank === 1).length;
    const isrank1Unique = rank1Count === 1;

    return (
        <div className="highscores-container">
            <h2 className="highscores-title">🏆 Council Leaderboard</h2>
            <div className="highscores-list">
                {rankedList.map((item, index) => (
                    <div key={item.model} className={`highscore-item rank-${item.rank} ${item.rank === 1 && isrank1Unique ? 'unique-winner' : ''}`}>
                        <div className="highscore-rank">{item.rank}</div>
                        <div className={`highscore-model`}>
                            {item.model}
                        </div>
                        <div className="highscore-score">{item.score} pts</div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Highscores;
