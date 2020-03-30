$(function() {
    $.getJSON("/countries", function(countryList) {
	var anyCountry = [{Code: "any", Id: NaN}],
	    selectedPlayers = new Object(), // hash of selected Player Id's
	    createMergeButton = function(item) {
		// merge icon: triple nested greater than ⫸ (u-2AF8)
		var selected = selectedPlayerIDs();
		return $("<input>").addClass(
		    "player-merge-button").attr({
			type: "button",
			title: "Merge selected players",
		    }).data("playerID", item.Id)
		    .css("display", 
			 selected.length > 1 && selectedPlayers[item.Id] ?
			 "inline" : "none").text("Merge").on(
			"click", function(e) {
			mergeSelectedPlayers(selectedPlayers, e);
			e.stopPropagation();
		    })
	    },
	    createPlayerSelectButton = function(editable) {
		return function(value, item) {
		    var box = this._createCheckbox().prop({
			  checked: item.Id && selectedPlayers[item.Id],
			  disabled: !editable
		    });
		    if (editable) { box.click(function (e) {
			  selectedPlayers[item.Id] = $(this).prop("checked");
			  players = selectedPlayerIDs();
			  updatePlayerMergeButtons();
			  e.stopPropagation();
		    })};
		    return box;
		}
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
		  inserting: false, editing: false, css: "PlayerSelectBox",
		  itemTemplate: createPlayerSelectButton(true),
		  editTemplate: createPlayerSelectButton(false), },
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
		return;
	    }
	    $.post(
		"/mergePlayers/", 
		JSON.stringify({playerIDs: players, performMerge: false}),
		function(resp) {
		    if (resp.status != 0) { $.notify(resp.message); return};
		    $.getJSON(
			"/playerslist/?players=" +
			    players.join("%20"),
			function(currentPlayers) {
			    if (currentPlayers.status != 0) {
				$.notify(currentPlayers.message); return};
			    confirmMerge(
				resp.merged, currentPlayers.data).done(
				    function(val) {
					if (!val) {
					    $.notify('Internal Error')
					}
					$.post("/mergePlayers/",
					       JSON.stringify(
						   {playerIDs: players,
						    performMerge: true}),
					       function(realmerge) {
						   if (realmerge.status != 0) {
						       $.notify(
							   realmerge.message);
						       return
						   };
						   clearSelectedPlayers();
						   $("#playersGrid")
						       .jsGrid("loadData");
					       });
				    });
			});
		});
 	};

	function confirmMerge(merged, players) {
	    var table = '<table class="confirm-merge-table">',
		columns=[], defer = $.Deferred();
	    table += '<thead><tr>';
	    for (key in merged) { 
		table += '<th>' + key + '</th>'; columns.push(key) };
	    table += '</tr></thead>  <tbody>' +
		players.map(function(o) {return copyObj(o, merged)})
		.map(function (player) {
		    var row = '<tr>';
		    for (key in merged) { 
			row += '<td>' + (player[key] || '') + '</td>' 
		    };
		    return row + '</tr>'
		});
	    table += '<tr><td colspan=' + columns.length + '>' +
		'will be merged into the player</td></tr>';
	    table += '<tr>' + columns.map(function (col) {
		return '<td>' + merged[col] + '</td>'; }) + '</tr>';
	    table += '<tr><td colspan=' + columns.length + '>' +
		'The operation cannot be undone. </td><tr>';
	    $.confirm({
		title: 'Confirm merge of ' + players.length + 
		    ' player records',
		useBootstrap: false,
		boxWidth: '80%',
		closeIcon: true,
		theme: 'dark',
		content: table,
		buttons: {
		    confirm: function () { defer.resolve(true) },
		    cancel: {
			text: 'Do not merge',
			btnClass: 'btn-blue',
			keys: ['enter', 'space'],
			action: function() { defer.reject(false) },
		    }
		},
	    });
	    return defer.promise();
	};

	function copyObj(obj, template) {
	    var result = new Object();
	    for (field in template) {result[field] = obj[field]};
	    return result
	};
	
	function objectToString(obj) {
	    var result = "";
	    for (field in obj) {
		if (result.length) { result += ", "}
		result += field + ": " + obj[field]
	    };
	    return "{" + result + "}"
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
