$(function() {
	withCountries(function() {
		$.getJSON("/authentication", function(auth) {
			var anyCountry = [{
					Code: "any",
					Id: NaN,
					Flag_Image: ""
				}],
				lastDatesItemEdited = null,
				selectedPlayers = new Object(), // hash of selected Player Id's
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
						insertValue: function() {
							return datesValue(this.insertControl)
						},
						editValue: function() {
							return datesValue(this.editControl)
						},
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
									$result = $result.add(createDuplicateButton(
										item, duplicateTournament, 'tournament'));
								}
							}
							return $result;
						},
						width: null,
					}
				],
				gridController = makeController(base + "tournamentList",
					tournamentfieldDescriptions);

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

			function datesTemplate(value, item) {
				return item.Start + ' - ' + item.End;
			};

			function datesEditTemplate(value, item) {
				var fields = ['Start', 'End'],
					dom = $('<div class="datepair">')
					.append('<span class="fieldlabel">Start:</span>')
					.append('<input class="startdate" type="text">')
					.append('<span class="fieldlabel">End:</span>')
					.append('<input class="enddate" type="text">')
				dom.find('input').each(function(i, field) {
					$(field).val(item && item[fields[i]] ? item[fields[i]] : null)
						.datepicker({
							dateFormat: "yy-mm-dd",
							showAnim: "slideDown",
							changeMonth: true,
							changeYear: true,
							defaultDate: i > 0 ? "+1d" : null,
						});
				});
				this[value === undefined && item === undefined ?
					'insertControl' : 'editControl'] = dom
				lastDatesItemEdited = item;
				return dom;
			};

			function datesValue(control) {
				var start = $(control).find("input.startdate").val(),
					end = $(control).find("input.enddate").val();
				if (start && end && lastDatesItemEdited &&
					'Start' in lastDatesItemEdited &&
					'End' in lastDatesItemEdited) {
					lastDatesItemEdited.Start = start;
					lastDatesItemEdited.End = end;
				};
				return start + ' - ' + end;
			};

			function tournamentItemInserting(obj) {
				var dateparts = obj.item.Dates && obj.item.Dates.split(' - ');
				if (dateparts && dateparts.length == 2) {
					obj.item.Start = dateparts[0];
					obj.item.End = dateparts[1];
				}
			};

			function playerSummaryTemplate(value, item) {
				var viewControl = $('<span class="playerviewcontrol jsgrid-button">')
					.data('tourneyid', item.Id).text('▶').click(togglePlayerView),
					summary = "";
				for (type in item.players) {
					if (item.players[type].length > 0) {
						if (summary.length > 0) {
							summary += ', '
						};
						summary += item.players[type].length + ' ' + type;
					}
				}
				return $('<span class="playersummary">').text(summary).prepend(viewControl);
			};

			function togglePlayerView(ev) {
				var on = $(this).hasClass('view-on');
				clearPlayerViews(this);
				if (!on) {
					$(this).addClass('view-on').text('▼');
					showPlayerView(this)
				};
				ev.stopPropagation();
			};

			function clearPlayerViews(button) {
				$(button).parents('#tournamentsGrid').find('.playerviewcontrol')
					.filter('.view-on').removeClass('view-on').text('▶');
			}

			function showPlayerView(button) {
				var row = $(button).parents('tr').first(),
					tourney = $(button).data('tourneyid');
				console.log('Show player view for tournament ' + tourney)
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
				deleteConfirm: 'Are you sure you want to delete this tournament?',
				controller: gridController,
				fields: tournamentfieldDescriptions,
				onItemInserting: tournamentItemInserting,
				onItemEditing: tournamentItemInserting,
			});
		});
	});
});
