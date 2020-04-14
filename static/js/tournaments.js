$(function() {
	var valueChangingKeys = {
		'Backspace': 1,
		'Delete': 1,
		'+': 1,
		'-': 1,
		'.': 1,
		'0': 1,
		'1': 1,
		'2': 1,
		'3': 1,
		'4': 1,
		'5': 1,
		'6': 1,
		'7': 1,
		'8': 1,
		'9': 1,
	};

	function onlyNumericKeys(eventHandler) { // Run an event handler only on keyboard events
		return function(ev) { //  that change numeric inputs
			if (ev && 'key' in ev && ev.key in valueChangingKeys) {
				eventHandler.apply(this, [ev])
			}
		}
	};
	withCountries(function() {
		$.getJSON("/authentication", function(auth) {
			var anyCountry = [{
					Code: "any",
					Id: NaN,
					Flag_Image: ""
				}],
				lastDatesItemEdited = null,
				selectedTourneyPlayers = new Object(), // hash of selected Player Id's
				selectedAvailablePlayers = new Object(), // for tourney and available
				tournamentsGridFieldWidth = 150,
				tournamentFieldDescriptions = [{
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
						css: "tourneynamefield",
						width: tournamentsGridFieldWidth * 2,
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
						css: "tourneydatesfield",
						width: tournamentsGridFieldWidth,
					},
					{
						name: "Location",
						type: "text",
						inserting: auth['user'],
						editing: auth['user'],
						css: "tourneylocationfield",
						width: tournamentsGridFieldWidth,
					},
					{
						name: "Country",
						type: "select",
						items: anyCountry.concat(countryList),
						inserting: auth['user'],
						editing: auth['user'],
						css: "tourneycountryfield",
						valueField: "Id",
						valueType: "number",
						textField: "Code",
						itemTemplate: countryTemplate,
						width: tournamentsGridFieldWidth,
					},
					{
						name: "Players",
						type: "text",
						editing: false,
						inserting: false,
						itemTemplate: playerSummaryTemplate,
						sorting: false,
						filtering: false,
						css: "playersummaryfield",
						width: tournamentsGridFieldWidth,
					},
					{
						type: "control",
						itemTemplate: function(value, item) {
							var $result = $([]);
							if (auth['user']) {
								var editOK = (auth['admin'] || auth['user'] == item.Owner);
								if (this.editButton && editOK) {
									$result = $result.add(
										this._createEditButton(item));
								}
								if (this.deleteButton && editOK) {
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
						css: "tourneycontrolfield",
						width: tournamentsGridFieldWidth * 3 / 4,
					}
				],
				tournamentsGridController = makeController(base + "tournamentList",
					tournamentFieldDescriptions),
				switchedtourneyfieldselectors = [],
				//				'.tourneylocationfield', '.tourneycontrolfield'],

				playerTypes = [],
				playerGridFieldWidth = 50,
				tourneyPlayerGridFields = [{
						name: "Type",
						type: "select",
						css: "playertypefield",
						items: playerTypes,
						inserting: false,
						editing: false,
						filtering: false,
						valueField: "Id",
						valueType: "number",
						textField: "Type",
						itemTemplate: playerTypeTemplate,
						width: playerGridFieldWidth,
					},
					{
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
						name: "Number",
						title: "#",
						type: "number",
						inserting: false,
						editing: false,
						css: "playernumberfield",
						itemTemplate: makePlayerFieldTemplate('Number', true),
						width: playerGridFieldWidth,
					},
					{
						name: "Pool",
						type: "text",
						inserting: false,
						editing: false,
						css: "playerpoolfield",
						itemTemplate: makePlayerFieldTemplate('Pool', false),
						width: playerGridFieldWidth,
					},
					{
						name: "Wheel",
						type: "number",
						inserting: false,
						editing: false,
						css: "playerwheelfield",
						itemTemplate: makePlayerFieldTemplate('Wheel', true),
						width: playerGridFieldWidth,
					},
					{
						name: "",
						type: "checkbox",
						width: "2em",
						inserting: false,
						editing: false,
						filtering: false,
						css: "playerselectboxfield",
						itemTemplate: createPlayerSelectButton(true, selectedTourneyPlayers),
						visible: auth['user'],
					},
				],
				tourneyPlayers = null,
				tourneyBeingEdited = null,
				availablePlayersGridFieldWidth = 100,
				availablePlayersGridFields = [{
						name: "Name",
						title: "Name / Association",
						type: "text",
						inserting: false,
						editing: false,
						itemTemplate: playerNameAssociationTemplate,
						css: "playernameassociationfield",
						width: availablePlayersGridFieldWidth && availablePlayersGridFieldWidth * 2,
					},
					{
						name: "",
						type: "checkbox",
						width: "2em",
						inserting: false,
						editing: false,
						filtering: false,
						css: "playerselectboxfield",
						itemTemplate: createPlayerSelectButton(true, selectedAvailablePlayers),
						visible: auth['user'],
					},
				],
				availablePlayersGridController = makeController(base + 'playerlist', availablePlayersGridFields);

			function createPlayerSelectButton(enable, playersObject) {
				return function(value, item) {
					var playerID = item.Player || item.Id;
					if (enable && item && !item.NumberScores) {
						return this._createCheckbox().prop({
								checked: false
							})
							.click(function(e) {
								playersObject[playerID] = $(this).prop("checked");
								e.stopPropagation();
							})
					}
					else {
						return ""
					}
				}
			};

			function datesTemplate(value, item) {
				return item.Start + ' - ' + item.End;
			};

			function datesEditTemplate(value, item) {
				var fields = ['Start', 'End'],
					forInsert = value === undefined && item === undefined,
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
				this[forInsert ? 'insertControl' : 'editControl'] = dom
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
					.data('tourney', item).text('▶').click(togglePlayerView),
					summary = $('<span class="playersummary">').data('item', item).data('tourneyid', item.Id)
					.text(playerTypeSummary(item.players));
				return $('<span class="playersummarywrapper">').append(viewControl).append(summary);
			};

			function playerTypeSummary(players) {
				var summary = '';
				for (type in players) {
					if (players[type].length > 0) {
						if (summary.length > 0) {
							summary += ', '
						};
						summary += players[type].length + ' ' + type;
					}
				}
				return summary.length == 0 ? "none" : summary;
			}

			function playerTypeTemplate(value, item) {
				var selector = $('<select class="playertypeselector">')
					.data('field', 'Type').data('item', item)
					.change(playerFieldChange);
				playerTypes.map(function(entry) {
					$("<option>").attr("value", entry.Id).text(entry.Type)
						.prop("selected", value == entry.Id).appendTo(selector);
				});
				return selector;
			};

			function makePlayerFieldTemplate(field, numeric) {
				return function(value, item) {
					if (auth['admin'] || auth['user'] == item.Owner) {
						return $('<input>').attr('type', numeric ? 'number' : 'text').val(value)
							.attr('size', 5).data('field', field).data('item', item)
							.change(playerFieldChange).keyup(
								numeric ? onlyNumericKeys(playerFieldChange) : playerFieldChange)
					}
					else {
						return value
					}
				}
			};

			function playerFieldChange(ev) {
				var control = $(this),
					field = $(this).data('field'),
					item = $(this).data('item'),
					newitem = copyObj(item);
				newitem[field] = control.val();
				if (control.attr('type') == 'number' && typeof(newitem[field]) == 'string') {
					newitem[field] = newitem[field] - 0;
				};
				control.parents('#tourneyplayersgrid').jsGrid("updateItem", newitem)
					.done(function() {
						item[field] = newitem[field];
						control.removeClass('bad');
						if (field == 'Type') {
							updatePlayerSummary()
						};
					})
					.fail(function() {
						control.addClass('bad')
					});
			};

			function updatePlayerSummary() {
				$('#tournamentsgrid .playersummary').each(function(i, elem) {
					if ($(elem).data('tourneyid') == tourneyBeingEdited.Id) {
						var players = $(elem).data('item').players;
						for (type in players) {
							players[type] = []
						};
						$('#tourneyplayersgrid .jsgrid-row').add('#tourneyplayersgrid .jsgrid-alt-row')
							.each(function(i, elem) {
								var competeItem = $(elem).data('JSGridItem');
								if (competeItem && playerTypes) {
									players[playerTypes[competeItem.Type || 0].Type].push(competeItem)
								}
							});
						$(elem).text(playerTypeSummary(players));
					}
				});
			};

			function playerNameAssociationTemplate(value, item) {
				var playerStatLink = $('<a>')
					.attr('href', base + 'playerStats/' + (item.Player || item.Id))
					.text(item.Name);
				return $('<span>').text(item.Association ? ' / ' + item.Association : '')
					.prepend(playerStatLink);
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
				$(button).parents('#tournamentsgrid').find('.playerviewcontrol')
					.filter('.view-on').removeClass('view-on').text('▶');
				$('.tourneyplayersrow').remove();
				$('#transferplayersbutton, #playerspanel').hide();
				$(switchedtourneyfieldselectors.join(', ')).show();
				$('#tournamentspanel').removeClass('tournamentplayereditmode');
				clearObject(selectedTourneyPlayers);
			}

			function showPlayerView(button) {
				var tourneyRow = $(button).parents('tr').first(),
					tourney = $(button).data('tourney'),
					playerList = [];
				if (auth['admin'] || auth['user'] == tourney.Owner) {
					$('#transferplayersbutton, #playerspanel').show().removeClass('hidden');
					$(switchedtourneyfieldselectors.join(', ')).hide();
					$('#tournamentspanel, #playerspanel').addClass('tournamentplayereditmode');
					tourneyBeingEdited = tourney;
				}
				tourneyPlayers = new Object();
				playerTypes = []; // NOTE: Assume entries in players are always in numeric order
				for (type in tourney.players) {
					playerTypes.push({
						'Type': type,
						'Id': playerTypes.length
					});
					tourney.players[type].map(function(player) {
						tourneyPlayers[player.Player] = 1;
						playerList.push(player);
					});
				};

				var grid = $('<div id="tourneyplayersgrid">').jsGrid({
						width: '90%',
						inserting: false,
						editing: false,
						sorting: true,
						filtering: true,
						confirmDeleting: false,
						data: playerList,
						controller: makeController(base + 'updatePlayerRole', tourneyPlayerGridFields, playerList),
						onItemDeleted: updateAvailablePlayers,
						onItemInserted: updateAvailablePlayers,
						paging: false,
						pageLoading: false,
						fields: tourneyPlayerGridFields,
						noDataContent: 'None found',
					}),
					label = $('<div class="sidelabelwrapper">').text('Players'),
					cell = $('<td>').attr('colspan', tournamentFieldDescriptions.filter(
						function(field) {
							return field.visible != false
						}).length).append(label).append(grid),
					innerRow = $('<tr class="tourneyplayersrow">')
					.addClass($(tourneyRow).hasClass('jsgrid-alt-row') ?
						'jsgrid-row' : 'jsgrid-alt-row').append(cell);
				$(tourneyRow).after(innerRow);
				updateAvailablePlayers();
			}

			function duplicateTournament(e) {
				var tourneyID = $(this).data('tourneyid');
				$.notify('Duplicate tournament ' + tourneyID);
				e.stopPropagation();
			};

			function updateAvailablePlayers() {
				$('#availableplayersgrid .jsgrid-row').add('#availableplayersgrid .jsgrid-alt-row')
					.each(function(i, elem) {
						var item = $(elem).data('JSGridItem');
						if (item && tourneyPlayers && tourneyPlayers[item.Id]) {
							$(elem).hide()
						}
						else {
							$(elem).find('.playerselectboxfield input[type="checkbox"]')
								.prop("checked", false);
							$(elem).show()
						};
					});
			};

			function transferSelectedPlayers() {
				transferPlayers(function() {
					updateAvailablePlayers();
					updatePlayerSummary()
				});
			};

			function transferPlayers(then) {
				if (tourneyBeingEdited) {
					var doneOne = false;
					for (player in selectedTourneyPlayers) {
						if (selectedTourneyPlayers[player]) {
							removePlayerFromTourney(player, tourneyBeingEdited.Id, then);
							doneOne = true;
							break;
						}
					};
					if (!doneOne) {
						for (player in selectedAvailablePlayers) {
							if (selectedAvailablePlayers[player]) {
								addPlayerToTourney(player, tourneyBeingEdited.Id, then);
								doneOne = true;
								break;
							}
						}
					};
					if (!doneOne) {
						then()
					}
				}
			};

			function removePlayerFromTourney(player, tourney, then) {
				var playerrow = null;
				$('#tourneyplayersgrid .jsgrid-row').add('#tourneyplayersgrid .jsgrid-alt-row')
					.each(function(i, elem) {
						item = $(elem).data('JSGridItem');
						if (item && item.Player == player) {
							playerrow = elem
						}
					});
				if (!playerrow) {
					$.notify('Internal error.  Could not find tournament player ' + player);
					return
				};
				$('#tourneyplayersgrid').jsGrid("deleteItem", playerrow).done(function() {
					delete selectedTourneyPlayers[player];
					delete tourneyPlayers[player];
					transferPlayers(then)
				});
			};

			function addPlayerToTourney(player, tourney, then) {
				var playerrow = null,
					pItem = null;
				$('#availableplayersgrid .jsgrid-row').add('#availableplayersgrid .jsgrid-alt-row')
					.each(function(i, elem) {
						item = $(elem).data('JSGridItem');
						if (item && item.Id == player) {
							playerrow = elem;
							pItem = item;
						}
					});
				if (!pItem) {
					$.notify('Internal error.  Could not find available player ' + player);
					return
				};
				var competitorItem = makeCompetitorEntry(pItem, tourney);
				$('#tourneyplayersgrid').jsGrid("insertItem", competitorItem).done(function() {
					delete selectedAvailablePlayers[player];
					tourneyPlayers[player] = 1;
					transferPlayers(then)
				});
			};

			function makeCompetitorEntry(item, tourney) {
				var entry = {
					Id: 0,
					Player: item.Id,
					Tournament: tourney,
					Number: null,
					Pool: null,
					Wheel: null,
					Type: null,
					NumberScores: 0
				};
				for (prop in item) {
					entry[prop] = item[prop]
				};
				return entry;
			};

			$("#tournamentsgrid").text('').jsGrid({
				height: "auto",
				// width: "700",
				inserting: auth['user'] ? true : false,
				editing: auth['user'] ? true : false,
				sorting: true,
				filtering: true,
				autoload: true,
				paging: false,
				pageLoading: false,
				deleteConfirm: function(item) {
					return 'Are you sure you want to delete the tournament "' + item.Name + '"?'
				},
				noDataContent: 'None found',
				controller: tournamentsGridController,
				fields: tournamentFieldDescriptions,
				onItemInserting: tournamentItemInserting,
				onItemEditing: tournamentItemInserting,
			});
			// if ($("#tournamentsgrid").css("width")) {$("#tournamentsgrid").css("width", "")}; HACK
			$("#availableplayersgrid").jsGrid({
				height: "800",
				width: "200",
				inserting: false,
				editing: false,
				sorting: true,
				filtering: true,
				autoload: true,
				paging: false,
				pageLoading: false,
				noDataContent: 'None found',
				controller: availablePlayersGridController,
				fields: availablePlayersGridFields,
				onDataLoaded: updateAvailablePlayers,
			});
			$('#transferplayersbutton').click(transferSelectedPlayers);
		});
	});
});
