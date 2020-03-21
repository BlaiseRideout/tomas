$(function() {
    $.getJSON("/countries", function(countryList) {
	var anyCountry = [{Code: "any", Id: NaN}], 
	    fieldDescriptions = [
            { name: "Id", type: "number", width: 5, visible: false },
            { name: "Name", type: "text", width: 150, validate: "required"},
            { name: "Association", type: "text", width: 40 },
            { name: "Country", type: "select", width: 30,
	      items: anyCountry.concat(countryList), css: "CountrySelector",
	      valueField: "Id", valueType: "number", textField: "Code", },
            { name: "Flag", type: "text", width: 20, css: "FlagImage",
	      editing: false, inserting: false, sorting: false,
	      filtering: false },
            { name: "Tournaments", type: "number", width: 45,
	      editing: false, inserting: false },
            { name: "Latest", type: "text", width: 50,
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
	    onItemUpdating: function(obj) {
		updateFlagImage(obj, countryList);
	    },
	    onItemUpdated: function(obj) { // Kluge to get data to show up
		$("#playersGrid").jsGrid("loadData");
	    },
	    onItemInserting: function(obj) {
		updateFlagImage(obj, countryList);
//		$("#playersGrid").jsGrid("loadData"); Kluge to get data to show
		$.notify(                             // KLUGE NOT WORKING
		    "Player record may be at end. Refesh page to see it"
		    , { position: "left" } );         // SO NOTIFY USER INSTEAD
	    },
	    onItemInseted: function(obj) { // THIS ISN'T CALLED EVEN THOUGH
		$("#playersGrid").jsGrid("loadData"); // THE DOCS SAY IT IS
	    },
        });
    });
    $(".playerListTitle").click(function() { // Click on grid title reloads
	$("#playersGrid").jsGrid("loadData"); // all the data
    });
});
