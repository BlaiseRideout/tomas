$(function() {
    var gridController = {
	loadData: function(filter) {
	    var d = $.Deferred();
            $.ajax({url: base + "playerslist/", dataType: "json"}).done(
		function(playersData) {
		    if (playersData.status != 0) {$.notify(playersData.message);}
		    else { d.resolve(playersData.data) }
		});
	    return d.promise();
	},	     
	updateItem: $.noop,
	deleteItem: $.noop,
	insertItem: $.noop,
    };
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
     
        fields: [
            { name: "Id", type: "number", width: 5, visible: false },
            { name: "Name", type: "text", width: 150, validate: "required"},
            { name: "Association", type: "text", width: 40 },
            { name: "Country", type: "text", width: 40 },
            { name: "Tournaments", type: "number", width: 40, editing: false },
            { name: "Latest", type: "text", width: 60, editing: false },
            { type: "control" }
        ]
        });
});
