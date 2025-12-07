```mermaid
flowchart TD
    %% Stili con testo nero forzato
    classDef start fill:#f9f,stroke:#333,stroke-width:2px,color:#000;
    classDef decision fill:#ff9,stroke:#333,stroke-width:2px,color:#000;
    classDef process fill:#fff,stroke:#333,stroke-width:1px,color:#000;
    classDef finish fill:#9f9,stroke:#333,stroke-width:2px,color:#000;
    classDef warning fill:#ffcccc,stroke:#b00,stroke-width:2px,color:#000;
    classDef safety fill:#ff6666,stroke:#300,stroke-width:2px,color:#000,stroke-dasharray: 5 5;
    classDef planner fill:#cce5ff,stroke:#003366,stroke-width:2px,color:#000;

    %% FASE 1: AVVIO E CHECK INIZIALE
    Root[Start: Ricezione Input]:::start --> InitBat{Batteria > 50%?}:::decision
    
    InitBat -->|No| Charge1[Ricarica Iniziale]:::warning
    Charge1 --> InitBat
    
    %% FASE 2: PIANIFICAZIONE GLOBALE
    InitBat -->|Sì| Prio[Calcolo Priorità di tutti i Pallet]:::planner
    Prio --> Order[Generazione Coda Missioni Ordinata]:::planner
    Order --> LoopCheck{La coda missioni <br>è vuota?}:::decision

    %% FASE 3: LOOP OPERATIVO
    LoopCheck -->|No - Prossimo Pallet| Pick["Estrai Pallet (Task attuale)"]:::process
    
    %% Preparazione percorso su linea
    Pick --> Path[Identifica percorso/bivii sulla linea]:::process

    %% BLOCCO NAVIGAZIONE (LINE FOLLOWER + SAFETY)
    Path --> Follow[Attiva Algoritmo Line Follower]:::process
    Follow --> Safe{Persona Rilevata?}:::safety
    
    Safe -->|Sì| Stop[Stop Motori]:::safety
    Stop --> Safe
    
    Safe -->|No| Arr{AprilTag rilevato /<br>Fine Linea?}:::decision
    Arr -->|No - Continua| Follow
    
    %% ARRIVO E AZIONE
    Arr -->|Sì - Arrivato| Align[Allineamento fine con AprilTag]:::process
    Align --> Action[Esegui Presa/Deposito]:::process
    
    %% CHECK BATTERIA INTERMEDIO
    Action --> PostBat{Batteria > 20%?}:::decision
    
    PostBat -->|Sì| LoopCheck
    
    %% Gestione ricarica
    PostBat -->|No| Charge2[Ricarica Intermedia]:::warning
    Charge2 --> LoopCheck

    %% FINE
    LoopCheck -->|Sì - Tutto Finito| End[Missione Completata]:::finish