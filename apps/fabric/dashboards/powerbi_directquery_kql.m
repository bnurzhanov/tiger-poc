// ==============================================================================
// Power BI DirectQuery over Microsoft Fabric KQL Database
// ==============================================================================
//
// Instructions for Power BI Desktop:
// 1. In Power BI Desktop, click "Get Data" -> "Azure" -> "Azure Data Explorer (Kusto)"
//    (or "Microsoft Fabric" -> "KQL Database").
// 2. Cluster URI: Enter your Fabric KQL Database Query URI (from Database Details).
// 3. Database Name: Enter your Eventhouse / KQL Database name.
// 4. Select "DirectQuery". This mode does not guarantee sub-second updates.
// 5. Select "CurrentPositionOccupancy", then "Transform Data". In Power Query's
//    "Advanced Editor", replace the query with the full M expression below and
//    update the endpoint/database placeholders. Connector query fields accept KQL,
//    not a complete M expression. Select "Done", then "Close & Apply".
// 6. In Report View, enable "Page refresh" for the page at a supported interval.
//    Five seconds is an optional target, subject to capacity/admin settings and
//    query duration. Verify the effective interval again after publishing.
// ==============================================================================

let
    // Replace with your Fabric KQL Database URI and Database Name
    ClusterUri = "https://<your-fabric-kusto-cluster-uri>.kusto.fabric.microsoft.com",
    DatabaseName = "<your-kql-database-name>",
    
    // DirectQuery M query joining streaming occupancy state with cell hierarchy
    Source = AzureDataExplorer.Contents(
        ClusterUri, 
        DatabaseName, 
        "CurrentPositionOccupancy | join kind=leftouter (MonitoredPositions | join kind=inner Cells on cellId | join kind=inner Plants on plantId) on $left.subjectId == $right.positionId | project Plant = plantName, Cell = cellName, Position = positionName, SubjectId = subjectId, ObservationType = observationType, IsOccupied = isOccupied, Status = iff(isOccupied, ""Occupied"", ""Empty""), Confidence = confidence, LastSeen = capturedAt, Camera = sourceId",
        [MaxRows=null, MaxSize=null, NoTruncate=null, AdditionalSetStatements=null]
    )
in
    Source
