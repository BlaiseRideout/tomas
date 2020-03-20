$(function() {
    var fieldDescriptions = [
        { name: "Id", type: "number", width: 5, visible: false },
        { name: "Name", type: "text", width: 150, validate: "required"},
        { name: "Association", type: "text", width: 40 },
        { name: "Country", type: "text", width: 40 },
        { name: "Tournaments", type: "number", width: 40,
	  editing: false, inserting: false },
        { name: "Latest", type: "text", width: 60,
	  editing: false, inserting: false },
        { type: "control" }
    ],
	gridController = makeController(base + "playerslist/",
					fieldDescriptions);
    $("#playersGrid").jsGrid({
        width: "100%",
        height: "auto",
     
        inserting: true,
        editing: true,
        sorting: true,
        filtering: true,
	autoload: true,
	paging: false,
	pageLoading: false,
	controller: gridController,
        fields: fieldDescriptions,
        });
});
