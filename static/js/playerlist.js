$(function() {
    $.getJSON("/countries", function(countryList) {
	var anyCountry = [{Code: "any", Id: NaN}],
	    selectedPlayers = new Object(), // hash of selected Player Id's
	    createMergeButton = function(item) {
		// merge icon: triple nested greater than ⫸ (u-2AF8)
		return $("<input>").addClass(
		    "player-merge-button").attr({
			type: "button",
			title: "Merge selected players",
		    }).data("playerID", item.Id)
		    .css("display", "none").text("⫸").on(
			"click", function(e) {
			mergeSelectedPlayers(selectedPlayers, e);
			e.stopPropagation();
		    })
	    },
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
		{ name: "", type: "checkbox", width: 10,
		  inserting: false, css: "PlayerSelectBox",
		  itemTemplate: function(value, item) {
		      return this._createCheckbox().prop({
			  checked: item.Id && selectedPlayers[item.Id],
			  disabled: false
		      }).click(function (e) {
			  selectedPlayers[item.Id] = $(this).prop("checked");
			  players = selectedPlayerIDs();
			  updatePlayerMergeButtons();
			  e.stopPropagation();
		      });
		  },
		},
		{ type: "control",
		  itemTemplate: function(value, item) {
		      var $result = $([]);
		      
		      if(this.editButton) {
			  $result = $result.add(this._createEditButton(item));
		      }

		      if(this.deleteButton &&
			 !item.Tournaments && !item.Scores) {
			  $result = $result.add(this._createDeleteButton(item));
		      }

		      $result = $result.add(createMergeButton(item));

		      return $result;
		  }
		}
	],
	    gridController = makeController(base + "playerslist/",
					    fieldDescriptions);
	
	function selectedPlayerIDs() {
	    var playerlist = [];
	    for (p in selectedPlayers) {
		if (selectedPlayers[p]) { playerlist.push(p) }};
	    return playerlist;
	};
	
	function clearSelectedPlayers() {
	    for (p in selectedPlayers) { delete selectedPlayers[p] };
	    $("#playersGrid .PlayerSelectBox input").prop("checked", false);
	};

	function updatePlayerMergeButtons() {
	    $("#playersGrid .player-merge-button").each(
		function(i, e) {
		    var id = $(e).data("playerID");
		    $(e).css("display",
			     players.length > 1 && selectedPlayers[id] ?
			     "inline" : "none")
		});
	};
	
	function mergeSelectedPlayers(selectedPlayers, e) {
	    players = selectedPlayerIDs();
	    if (players.length < 2) {
		$.notify('Merge requires 2 or more players')
	    } else if (window.confirm(
		'OK to merge ' + players.length + ' players?')) {
		console.log('Merge players with IDs: ', players.join(', '));
		clearSelectedPlayers();
		updatePlayerMergeButtons();
	    }
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
            fields: fieldDescriptions,
	    onItemUpdating: function(obj) {
		updateFlagImage(obj, countryList);
	    },
	    onItemInserting: function(obj) {
		updateFlagImage(obj, countryList);
	    },
        });
    });
    $(".playerListTitle").click(function() { // Click on grid title reloads
	$("#playersGrid").jsGrid("loadData"); // all the data
    });
});
