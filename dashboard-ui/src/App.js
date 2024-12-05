import logo from './logo.png';
import './App.css';
import React from 'react';

import EndpointAnalyzer from './components/EndpointAnalyzer'
import AppStats from './components/AppStats'

function App() {

    const endpoints = ["users/reviews/rating_game", "users/user_reviews"]
    const rendered_endpoints = endpoints.map((endpoint) => {
        return <EndpointAnalyzer key={endpoint} endpoint={endpoint}/>
    })

    const anomalies = ["Too Many Ratings", "Too Few Reviews"];
    const rendered_anomalies = anomalies.map((anomaly) => {
        return <EndpointAnalyzer key={anomaly} endpoint={anomaly}/>
    })

    return (
        <div className="App">
            <img src={logo} className="App-logo" alt="logo" height="150px" width="400px"/>
            <div>
                <AppStats/>
                <h1>Analyzer Endpoints</h1>
                {rendered_endpoints}
                <h1>Anomalies</h1>
                {rendered_anomalies}
            </div>
        </div>
    );

}



export default App;
