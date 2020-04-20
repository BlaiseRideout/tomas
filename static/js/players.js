$(function() {
	withCountries(function() {

		var playerTypes = [],
			playerGridFieldWidth = 50,
			tourneyPlayerGridFields = [{
					name: "Name",
					title: "Name / Association",
					type: "text",
					inserting: false,
					editing: false,
					itemTemplate: playerNameAssociationTemplate,
					css: "playernameassociationfield",
					width: playerGridFieldWidth && playerGridFieldWidth * 2,
				},
				{
					name: "Country",
					type: "text",
					width: playerGridFieldWidth,
					css: "playercountryfield",
					inserting: false,
					editing: false,
					filtering: false,
					itemTemplate: countryTemplate,
				},
				{
					name: "Number",
					title: "#",
					type: "number",
					inserting: false,
					editing: false,
					css: "playernumberfield",
					width: playerGridFieldWidth,
				},
				{
					name: "Pool",
					type: "text",
					inserting: false,
					editing: false,
					css: "playerpoolfield",
					width: playerGridFieldWidth,
				},
				{
					name: "Wheel",
					type: "number",
					inserting: false,
					editing: false,
					css: "playerwheelfield",
					width: playerGridFieldWidth,
				},
				{
					name: "Type",
					type: "text",
					css: "playertypefield",
					inserting: false,
					editing: false,
					filtering: false,
					itemTemplate: playerTypeTemplate,
					width: playerGridFieldWidth,
				},
			];

		function loadTourneyPlayerData(filterItem) {
			var d = $.Deferred();
			$.ajax({
				url: base + 'tournamentList?tournament=' + tournamentid,
				dataType: "json"
			}).done(
				function(loadData) { // Return has status = 0 for success
					if (loadData.status != 0) {
						$.notify(loadData.message);
						d.reject();
					}
					else {
						var playerHist = loadData.data[0].players,
							players = [];
						playerTypes = []; // NOTE: Assume entries in players are always in numeric order
						for (type in playerHist) {
							playerTypes.push({
								'Type': type,
								'Id': playerTypes.length
							});
							players = players.concat(playerHist[type]);
						}
						d.resolve(players.filter(
							makeFilter(filterItem, tourneyPlayerGridFields)))
					}
				});
			return d.promise();
		};

		function playerTypeTemplate(value, item) {
			var playerType = '';
			playerTypes.map(function(entry) {
				if (value == entry.Id) {
					playerType = entry.Type
				}
			});
			return playerType;
		};

		$('#tourneyplayersgrid').text('').jsGrid({
			width: '100%',
			inserting: false,
			editing: false,
			sorting: true,
			filtering: true,
			confirmDeleting: false,
			controller: {
				loadData: loadTourneyPlayerData
			},
			paging: false,
			pageLoading: false,
			autoload: true,
			fields: tourneyPlayerGridFields,
			noDataContent: 'None found',
		});
	});
	$("#tournament").tabs({
		activate: function(event, ui) {
			if (ui && ui.newTab && ui.newTab.data('id') == 'players') {
				$('#tourneyplayersgrid').jsGrid("loadData");
			}
		},
	})
});
