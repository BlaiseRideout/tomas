$(function() {
	$.getJSON("/countries", function(countryList) {
		$.getJSON("/authentication", function(auth) {
			var anyCountry = [{
					Code: "any",
			    Id: NaN,
			    Flag_Image: ""
				}],
				selectedPlayers = new Object(), // hash of selected Player Id's
				createDuplicateButton = function(item) {
					var selected = selectedPlayerIDs();
				    return $('<span class="duplicate-icon-tl" title="Duplicate tournament">')
					.data('tourneyid', item.Id)
					.text('📄').append('<span class="duplicate-icon-br">')
					.text('📄').on('click', duplicateTournament)
				},
				createPlayerSelectButton = function(editable) {
					return function(value, item) {
						var box = this._createCheckbox().prop({
							checked: item.Id && selectedPlayers[item.Id],
							disabled: !editable
						});
						if (editable) {
							box.click(function(e) {
								selectedPlayers[item.Id] = $(this).prop("checked");
								players = selectedPlayerIDs();
								e.stopPropagation();
							})
						};
						return box;
					}
				},
				tournamentfieldDescriptions = [{
						name: "Id",
						type: "number",
				                visible: false
					},
					{
						name: "Name",
						type: "text",
						inserting: auth['user'],
						editing: auth['user'],
						validate: "required",
						itemTemplate: tournamentLinkTemplate,
					    width: null,
					},
					{
						name: "Dates",
						type: "text",
						inserting: auth['user'],
					    editing: auth['user'],
					    itemTemplate: datesTemplate,
					    editTemplate: datesEditTemplate,
					    insertTemplate: datesEditTemplate,
					    editValue: datesEditValue,
					    width: null,
					},
					{
						name: "Location",
						type: "text",
						inserting: auth['user'],
						editing: auth['user'],
					    width: null,
					},
					{
						name: "Country",
						type: "select",
						items: anyCountry.concat(countryList),
						inserting: auth['user'],
						editing: auth['user'],
						css: "CountrySelector",
						valueField: "Id",
						valueType: "number",
					    textField: "Code",
					    itemTemplate: countryTemplate,
					    width: null,
					},
					{
						name: "Players",
						type: "text",
						editing: false,
					    inserting: false,
					    itemTemplate: playerSummaryTemplate,
						sorting: false,
					    filtering: false,
					    width: null,
					},
					{
						type: "control",
						itemTemplate: function(value, item) {
						    var $result = $([]);
						    if (auth['user']) {
							if (this.editButton && auth['user'] == item.Owner) {
								$result = $result.add(
									this._createEditButton(item));
							}
							if (this.deleteButton && (auth['admin'] || auth['user'] == item.Owner)) {
								$result = $result.add(
									this._createDeleteButton(item));
							}
							if (auth['user']) {
								$result = $result.add(createDuplicateButton(item));
							}}
						    return $result;
						},
					    width: null,
					}
				],
				gridController = makeController(base + "tournamentList",
								tournamentfieldDescriptions),
			    countries = Array(countryList.length + 1);
		    for (j = 0; j < countryList.length; j++) {
			countries[countryList[j].Id] = countryList[j]
		    };
			function selectedPlayerIDs() {
				var playerlist = [];
				for (p in selectedPlayers) {
					if (selectedPlayers[p]) {
						playerlist.push(p)
					}
				};
				return playerlist;
			};

			function clearSelectedPlayers() {
				for (p in selectedPlayers) {
					delete selectedPlayers[p]
				};
				$("#playersGrid .PlayerSelectBox input").prop("checked", false);
			};

		    function datesTemplate (value, item) {
			return item.Start + ' - ' + item.End;
		    };
		    
		    function datesEditTemplate (value, item) {
			var fields = ['Start', 'End'],
			    dom = $('<div class="datepair">')
			    .append('<span class="fieldlabel">Start:</span>')
			    .append('<input class="startdate" type="text">')
			    .append('<span class="fieldlabel">End:</span>')
			    .append('<input class="enddate" type="text">')
			dom.find('input').each(function (i, field) {
			    $(field).val(item && item[fields[i]] ? item[fields[i]] : null)
			    .datepicker({
				dateFormat: "yy-mm-dd", showAnim: "slideDown",
				changeMonth: true, changeYear: true,
				defaultDate: i > 0 ? "+1d" : null,
			    });
			});
			return dom;
		    };

		    function datesEditValue () {
			var start = $(this).find("input.startdate").val(),
			    end = $(this).find("input.enddate").val();
			return start + ' - ' + end;
		    }
		    
		    function playerSummaryTemplate (value, item) {
			var summary = "";
			for (type in item.players) {
			    if (item.players[type].length > 0) {
				if (summary.length > 0) {summary += ', '};
				summary += item.players[type].length + ' ' + type;
			    }
			}
			return summary;
		    };

		    function countryTemplate (value, item) {
			var flag = $('<span class="flagimage">').html(countries[value].Flag_Image);
			return $('<span class="countrypair">').text(countries[value].Code).append(flag);
		    }

		    function duplicateTournament(e) {
			var tourneyID = $(this).data('tourneyid');
			$.notify('Duplicate tournament ' + tourneyID);
			e.stopPropagation();
		    };
		        
		    $("#tournamentsGrid").text('').jsGrid({
				height: "auto",

				inserting: auth['user'] ? true : false,
				editing: auth['user'] ? true : false,
				sorting: true,
				filtering: true,
				autoload: true,
				paging: false,
				pageLoading: false,
				controller: gridController,
				fields: tournamentfieldDescriptions,
			});
		});
	});
});
