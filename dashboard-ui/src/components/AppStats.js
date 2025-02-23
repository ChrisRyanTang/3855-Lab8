import React, { useEffect, useState } from 'react'
import '../App.css';

export default function AppStats() {
    const [isLoaded, setIsLoaded] = useState(false);
    const [stats, setStats] = useState({});
    const [error, setError] = useState(null)

    const [anomalies, setAnomalies] = useState([]);
    const [eventType, setEventType] = useState('get_all_reviews', 'rating_game');
    const [anomaliesLoaded, setAnomaliesLoaded] = useState(false);
    const [anomaliesError, setAnomaliesError] = useState(null);

	const getStats = () => {
	
        fetch(`http://kafka-3855.westus2.cloudapp.azure.com:8100/stats`)
            .then(res => res.json())
            .then((result)=>{
				console.log("Received Stats")
                setStats(result);
                setIsLoaded(true);
            },(error) =>{
                setError(error)
                setIsLoaded(true);
            })
    }

    const getAnomalies = () => {
        fetch(`http://kafka-3855.westus2.cloudapp.azure.com:8120/anomalies?anomaly_type=${eventType}`)
            .then((res) => res.json())
            .then((result) => {
                console.log('Received Anomalies');
                
                // Filter to get the most recent anomaly for each type
                const latestAnomaliesMap = new Map();
                result.forEach(anomaly => {
                    const anomalyType = anomaly.anomaly_type;
                    if (!latestAnomaliesMap.has(anomalyType) || 
                        new Date(latestAnomaliesMap.get(anomalyType).timestamp) < new Date(anomaly.timestamp)) {
                        latestAnomaliesMap.set(anomalyType, anomaly);
                    }
                });
    
                // Convert the Map back to an array
                const latestAnomalies = Array.from(latestAnomaliesMap.values());
    
                setAnomalies(latestAnomalies);
                setAnomaliesLoaded(true);
            }, (error) => {
                setAnomaliesError(error);
                setAnomaliesLoaded(true);
            });
    };
    

    useEffect(() => {
        const statsInterval = setInterval(() => getStats(), 2000); // Update stats every 2 seconds
        const anomaliesInterval = setInterval(() => getAnomalies(), 5000); // Update anomalies every 5 seconds
        return () => {
            clearInterval(statsInterval);
            clearInterval(anomaliesInterval);
        };
    }, [eventType]);

    useEffect(() => {
        getAnomalies();
    }, [eventType]); 

    if (error) {
        return <div className="error">Error fetching stats from API</div>;
    } else if (isLoaded === false) {
        return <div>Loading stats...</div>;
    }

    return (
        <div>
            <h1>Latest Stats</h1>
            <table className="StatsTable">
                <tbody>
                    <tr>
                        <th>Game Ratings</th>
                        <th>Game Reviews</th>
                    </tr>
                    <tr>
                        <td># Rating: {stats['num_ratings']}</td>
                        <td># Review: {stats['num_reviews']}</td>
                    </tr>
                    <tr>
                        <td colSpan="2">Max Number of ratings: {stats['num_ratings']}</td>
                    </tr>
                    <tr>
                        <td colSpan="2">Max Number of reviews: {stats['num_reviews']}</td>
                    </tr>
                </tbody>
            </table>
            <h3>Last Updated: {stats['last_updated']}</h3>

            <h2>Anomalies</h2>
            <label htmlFor="eventType">Event Type:</label>
            <select
                id="eventType"
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
            >
                <option value="get_all_reviews">Get All Reviews</option>
                <option value="rating_game">Rating Game</option>
            </select>

            {anomalies.length > 0 ? (
                    <table className={"AnomaliesTable"}>
                        <thead>
                            <tr>
                                <th>Trace ID</th>
                                <th>Anomaly Type</th>
                                <th>Description</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>
                            {anomalies.map((anomaly, index) => (
                                <tr key={index}>
                                    <td>{anomaly.trace_id}</td>
                                    <td>{anomaly.anomaly_type}</td>
                                    <td>{anomaly.description}</td>
                                    <td>{anomaly.timestamp}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <div>No anomalies found for event type "{eventType}".</div>
                )}
            </div>
        );
}